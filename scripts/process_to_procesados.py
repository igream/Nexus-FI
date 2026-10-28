import os
import json
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Any, Tuple

from nexus_ingestion.config import config
from nexus_ingestion.classifier import DocumentClassifier
from nexus_ingestion.chunker import StructuralChunker
from nexus_ingestion.extractors.ocr_engine import get_ocr_engine
from nexus_ingestion.extractors.pdf_extractor import PDFExtractor
from nexus_ingestion.extractors.html_extractor import HTMLExtractor
from nexus_ingestion.extractors.text_normalizer import normalize_text

BASE_DIR = Path(__file__).resolve().parent.parent
BASE_INPUT = str(BASE_DIR / "Pre Procesados")
BASE_OUTPUT = str(BASE_DIR / "Procesados")
TEMPLATE_FILE = str(BASE_DIR / "docs" / "plantilla_coordinacion_ico.md")

_worker_pdf: PDFExtractor = None
_worker_html: HTMLExtractor = None
_worker_classifier: DocumentClassifier = None
_worker_chunker: StructuralChunker = None


def init_worker():
    global _worker_pdf, _worker_html, _worker_classifier, _worker_chunker
    ocr = get_ocr_engine(provider=config.ocr_provider, region=config.aws_region)
    _worker_pdf = PDFExtractor(
        ocr_engine=ocr,
        max_file_size_mb=config.max_file_size_mb,
        max_pdf_pages=config.max_pdf_pages,
    )
    _worker_html = HTMLExtractor(max_file_size_mb=config.max_file_size_mb)
    _worker_classifier = DocumentClassifier()
    _worker_chunker = StructuralChunker(
        target_tokens=config.chunk_size_tokens,
        overlap_tokens=config.chunk_overlap_tokens,
        min_tokens=config.min_chunk_tokens,
        max_tokens=config.max_chunk_tokens,
    )


def _escape_yaml_str(val: Any) -> str:
    s = str(val).replace("\\", "/").replace('"', '\\"').replace("\n", " ").replace("\r", "")
    return f'"{s}"'


def process_single_file(item: Tuple[str, str]) -> Dict[str, Any]:
    """Procesa un archivo individual y lo almacena estructurado en /Procesados."""
    global _worker_pdf, _worker_html, _worker_classifier, _worker_chunker
    if _worker_chunker is None:
        init_worker()

    full_path, rel_path = item
    doc_name = os.path.basename(full_path)
    ext = os.path.splitext(full_path)[1].lower()

    initial_info = _worker_classifier.classify(rel_path)
    cat_dir = initial_info["cat_dir"]
    clean_name = initial_info["clean_name"]

    target_dir = os.path.join(BASE_OUTPUT, cat_dir)
    os.makedirs(target_dir, exist_ok=True)

    json_path = os.path.join(target_dir, f"{clean_name}.json")
    md_path = os.path.join(target_dir, f"{clean_name}.md")

    if os.path.exists(json_path) and os.path.exists(md_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            return {
                "file": rel_path,
                "status": "cached",
                "chunks": data.get("chunks", []),
                "pages": meta.get("total_paginas", 0),
                "is_ocr": meta.get("es_ocr", False),
                "categoria": meta.get("categoria", initial_info["categoria"]),
                "metadata": meta,
            }
        except Exception:
            pass

    t0 = time.time()
    try:
        if ext == ".pdf":
            pages_content = _worker_pdf.extract(full_path)
        elif ext in (".html", ".htm"):
            pages_content = _worker_html.extract(full_path)
        elif ext in (".md", ".txt"):
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            norm = normalize_text(content)
            pages_content = [{"page_number": 1, "text": norm, "is_ocr": False}] if norm else []
        else:
            pages_content = []
    except Exception as e:
        print(f"[ERROR procesando {rel_path}]: {e}")
        return {"file": rel_path, "status": "error", "error": str(e), "chunks": []}

    if not pages_content:
        return {"file": rel_path, "status": "empty", "chunks": []}

    es_ocr_doc = any(p.get("is_ocr", False) for p in pages_content)
    sample_text = "\n".join(p["text"] for p in pages_content[:2])
    classified = _worker_classifier.classify(rel_path, sample_text=sample_text)

    meta = {
        "id": classified["id"],
        "clean_id": classified["clean_id"],
        "titulo": classified["titulo"],
        "documento_original": doc_name,
        "ruta_relativa_fuente": rel_path.replace("\\", "/"),
        "categoria": classified["categoria"],
        "subcategoria": classified["subcategoria"],
        "carrera": classified["carrera"],
        "periodo": classified["periodo"],
        "total_paginas": len(pages_content),
        "es_ocr": es_ocr_doc,
        "fecha_procesamiento": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    chunks = _worker_chunker.chunk_document(doc_name, pages_content, meta)
    total_tokens = sum(c["token_count"] for c in chunks)
    meta["total_tokens"] = total_tokens
    meta["total_chunks"] = len(chunks)

    md_lines = [
        "---",
        f"id: {_escape_yaml_str(meta['id'])}",
        f"titulo: {_escape_yaml_str(meta['titulo'])}",
        f"categoria: {_escape_yaml_str(meta['categoria'])}",
        f"subcategoria: {_escape_yaml_str(meta['subcategoria'])}",
        f"carrera: {_escape_yaml_str(meta['carrera'])}",
        f"periodo: {_escape_yaml_str(meta['periodo'])}",
        f"archivo_fuente: {_escape_yaml_str(meta['ruta_relativa_fuente'])}",
        f"total_paginas: {int(meta['total_paginas'])}",
        f"es_ocr: {str(bool(meta['es_ocr'])).lower()}",
        f"total_tokens: {int(meta['total_tokens'])}",
        f"total_chunks: {int(meta['total_chunks'])}",
        "---",
        "",
        f"# {meta['titulo']}",
        "",
    ]
    for p in pages_content:
        md_lines.append(f"<!-- Página {p['page_number']} -->")
        md_lines.append(p["text"])
        md_lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    doc_json = {
        "metadata": meta,
        "pages": pages_content,
        "chunks": chunks,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(doc_json, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t0
    ocr_tag = "[OCR]" if es_ocr_doc else "[DIGITAL]"
    print(f"  {ocr_tag} {clean_name[:40]:40} | Págs: {len(pages_content):3d} | Chunks: {len(chunks):3d} | {elapsed:.1f}s")

    return {
        "file": rel_path,
        "status": "success",
        "chunks": chunks,
        "pages": len(pages_content),
        "is_ocr": es_ocr_doc,
        "categoria": meta["categoria"],
        "metadata": meta,
    }


def main():
    print("=" * 80)
    print("NEXUS FI — PROCESAMIENTO Y NORMALIZACIÓN LOCAL DE DOCUMENTOS")
    print(f"Destino: {BASE_OUTPUT}")
    print("=" * 80)

    os.makedirs(BASE_OUTPUT, exist_ok=True)

    files_to_process = []
    if os.path.exists(BASE_INPUT):
        for root, _, files in os.walk(BASE_INPUT):
            for f in sorted(files):
                if f.lower().endswith((".pdf", ".html", ".htm")):
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, BASE_INPUT)
                    files_to_process.append((full_p, rel_p))

    if os.path.exists(TEMPLATE_FILE):
        files_to_process.append((TEMPLATE_FILE, "plantilla_coordinacion_ico.md"))

    print(f"Total de documentos a procesar: {len(files_to_process)}")

    t_start = time.time()
    all_chunks = []
    doc_manifest = []
    stats = {
        "total_documentos": len(files_to_process),
        "procesados_exito": 0,
        "total_paginas": 0,
        "total_chunks": 0,
        "total_tokens": 0,
        "documentos_ocr": 0,
        "documentos_digitales": 0,
        "por_categoria": {},
    }

    workers = max(1, config.max_workers)
    print(f"\nIniciando procesamiento concurrente en {workers} núcleo(s)...")
    with ProcessPoolExecutor(max_workers=workers, initializer=init_worker) as executor:
        futures = {executor.submit(process_single_file, item): item for item in files_to_process}

        for future in as_completed(futures):
            res = future.result()
            if res.get("status") in ("success", "cached") and res.get("chunks"):
                stats["procesados_exito"] += 1
                stats["total_paginas"] += res.get("pages", 0)
                stats["total_chunks"] += len(res["chunks"])

                if res.get("is_ocr"):
                    stats["documentos_ocr"] += 1
                else:
                    stats["documentos_digitales"] += 1

                cat = res.get("categoria", "general")
                stats["por_categoria"][cat] = stats["por_categoria"].get(cat, 0) + len(res["chunks"])

                all_chunks.extend(res["chunks"])
                if "metadata" in res:
                    doc_manifest.append(res["metadata"])

    stats["total_tokens"] = sum(c["token_count"] for c in all_chunks)
    total_elapsed = time.time() - t_start

    jsonl_path = os.path.join(BASE_OUTPUT, "corpus_chunks_para_embedding.jsonl")
    print(f"\nEscribiendo {len(all_chunks)} chunks unificados en {jsonl_path}...")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    manifest_path = os.path.join(BASE_OUTPUT, "manifest.json")
    manifest_data = {
        "fecha_generacion": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tiempo_procesamiento_segundos": round(total_elapsed, 2),
        "estadisticas_globales": stats,
        "documentos": doc_manifest,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"PROCESAMIENTO COMPLETADO EN {total_elapsed:.1f} SEGUNDOS ({total_elapsed / 60:.2f} MINUTOS)")
    print(f"Total Documentos Procesados : {stats['procesados_exito']} / {stats['total_documentos']}")
    print(f"Documentos con OCR Local    : {stats['documentos_ocr']}")
    print(f"Documentos Digitales Nativos: {stats['documentos_digitales']}")
    print(f"Total Páginas Procesadas    : {stats['total_paginas']}")
    print(f"Total Chunks Listos         : {stats['total_chunks']}")
    print(f"Total Tokens Estimados      : {stats['total_tokens']:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
