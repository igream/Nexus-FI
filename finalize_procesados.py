import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from nexus_ingestion.classifier import clean_filename
from nexus_ingestion.chunker import StructuralChunker
from nexus_ingestion.extractors.text_normalizer import normalize_text

BASE_DIR = Path(__file__).resolve().parent
BASE_PROCESSED = str(BASE_DIR / "Procesados")
_chunker = StructuralChunker(target_tokens=650, overlap_tokens=100, min_tokens=100, max_tokens=800)


def strict_chunking(
    doc_name: str,
    pages: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    target_tokens: int = 650,
    overlap_tokens: int = 100,
) -> List[Dict[str, Any]]:
    """Wrapper compatible hacia StructuralChunker de nexus_ingestion."""
    chunker = (
        _chunker
        if (target_tokens == 650 and overlap_tokens == 100)
        else StructuralChunker(target_tokens=target_tokens, overlap_tokens=overlap_tokens)
    )
    return chunker.chunk_document(doc_name, pages, metadata)


def _escape_yaml_str(val: Any) -> str:
    """Escapa comillas y saltos de línea para evitar inyección/corrupción en YAML Frontmatter."""
    s = str(val).replace("\\", "/").replace('"', '\\"').replace("\n", " ").replace("\r", "")
    return f'"{s}"'


def main():
    print("=" * 80)
    print("REORGANIZANDO Y OPTIMIZANDO /Procesados CON NOMBRES CANÓNICOS Y CHUNKS RF08")
    print("=" * 80)

    all_json_files = []
    for root, _, files in os.walk(BASE_PROCESSED):
        for f in sorted(files):
            if f.endswith(".json") and f != "manifest.json":
                all_json_files.append(os.path.join(root, f))

    print(f"Total documentos encontrados: {len(all_json_files)}")

    all_chunks = []
    doc_manifest = []
    files_to_remove = []

    stats = {
        "total_documentos": len(all_json_files),
        "total_paginas": 0,
        "total_chunks": 0,
        "total_tokens": 0,
        "documentos_ocr": 0,
        "documentos_digitales": 0,
        "por_categoria": {},
    }

    for json_file in all_json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            doc_data = json.load(f)

        meta = doc_data["metadata"]
        pages = doc_data["pages"]
        orig_doc = meta["documento_original"]

        # Normalizar texto de cada página con las reglas unificadas
        for p in pages:
            p["text"] = normalize_text(p.get("text", ""))

        clean_name = clean_filename(orig_doc)
        parent_dir = os.path.dirname(json_file)
        new_json_path = os.path.join(parent_dir, f"{clean_name}.json")
        new_md_path = os.path.join(parent_dir, f"{clean_name}.md")

        if os.path.normcase(json_file) != os.path.normcase(new_json_path):
            files_to_remove.append(json_file)
            old_md = os.path.splitext(json_file)[0] + ".md"
            if os.path.exists(old_md):
                files_to_remove.append(old_md)

        clean_id = f"{meta['carrera'].lower()}_{clean_name}".lower()[:60]
        meta["id"] = clean_id
        meta["clean_id"] = clean_id
        meta["titulo"] = os.path.splitext(orig_doc)[0]

        chunks = strict_chunking(orig_doc, pages, meta)
        meta["total_tokens"] = sum(c["token_count"] for c in chunks)
        meta["total_chunks"] = len(chunks)
        meta["total_paginas"] = len(pages)

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
        for p in pages:
            md_lines.append(f"<!-- Página {p['page_number']} -->")
            md_lines.append(p["text"])
            md_lines.append("")

        with open(new_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        new_doc_json = {
            "metadata": meta,
            "pages": pages,
            "chunks": chunks,
        }
        with open(new_json_path, "w", encoding="utf-8") as f:
            json.dump(new_doc_json, f, indent=2, ensure_ascii=False)

        stats["total_paginas"] += len(pages)
        stats["total_chunks"] += len(chunks)
        stats["total_tokens"] += meta["total_tokens"]
        if meta["es_ocr"]:
            stats["documentos_ocr"] += 1
        else:
            stats["documentos_digitales"] += 1

        cat = meta["categoria"]
        stats["por_categoria"][cat] = stats["por_categoria"].get(cat, 0) + len(chunks)

        all_chunks.extend(chunks)
        doc_manifest.append(meta)

    for old_f in files_to_remove:
        if os.path.exists(old_f):
            os.remove(old_f)

    jsonl_path = os.path.join(BASE_PROCESSED, "corpus_chunks_para_embedding.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    manifest_path = os.path.join(BASE_PROCESSED, "manifest.json")
    manifest_data = {
        "fecha_generacion": time.strftime("%Y-%m-%d %H:%M:%S"),
        "estadisticas_globales": stats,
        "documentos": doc_manifest,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"Eliminados {len(files_to_remove)} archivos antiguos con nombres distorsionados.")
    print("=" * 80)
    print("ORGANIZACIÓN Y CHUNKING FINALIZADOS CON ÉXITO")
    print(f"Total Documentos: {stats['total_documentos']}")
    print(f"Total Páginas: {stats['total_paginas']}")
    print(f"Total Chunks Estrictos (RF08): {stats['total_chunks']}")
    print(f"Total Tokens: {stats['total_tokens']:,}")
    print(f"Desglose por categoría: {stats['por_categoria']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
