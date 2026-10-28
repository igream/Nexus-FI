import hashlib
import re
from typing import List, Dict, Any, Tuple
import tiktoken
from .classifier import clean_filename

_ARTICULO_REGEX = re.compile(
    r"(Art[íi]culo\s+\d+[\w\.\-]*|Cap[íi]tulo\s+[IVXLCDM\d]+|T[íi]tulo\s+[IVXLCDM\d]+)",
    re.IGNORECASE,
)


class StructuralChunker:
    """
    Segmentador semántico estricto alineado con RF08 y RF09 del proyecto Nexus FI:
    - Garantiza fragmentos totales (incluyendo cabecera) <= max_tokens (800 tokens por defecto).
    - Aplica overlap exacto acotado por ventana de tokens (overlap_tokens = 100), evitando
      desbordamientos cuando el último párrafo es extenso.
    - Propaga el Artículo / Capítulo vigente entre fragmentos contiguos.
    - Fusiona fragmentos huérfanos finales (< min_tokens = 100) cuando caben en el chunk previo.
    - Genera chunk_id determinista y hash SHA-256 de contenido para idempotencia.
    """

    def __init__(
        self,
        target_tokens: int = 650,
        overlap_tokens: int = 100,
        min_tokens: int = 100,
        max_tokens: int = 800,
    ):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    @staticmethod
    def _build_header(doc_name: str, categoria: str, start_p: int, end_p: int, articulo: str) -> str:
        return (
            f"[DOCUMENTO: {doc_name} | CATEGORÍA: {categoria.upper()} | "
            f"PÁG: {start_p}-{end_p}"
            f"{' | ' + articulo if articulo else ''}]\n\n"
        )

    def _compute_overlap(
        self,
        items: List[Tuple[int, str, List[int]]],
        overlap_budget: int,
    ) -> List[Tuple[int, str, List[int]]]:
        """
        Construye el solapamiento exacto <= overlap_budget tokens a partir del final
        del chunk actual, preservando el número de página real de cada pasaje.
        """
        if overlap_budget <= 0 or not items:
            return []

        overlap_items: List[Tuple[int, str, List[int]]] = []
        acc_tokens = 0

        for p_num, txt, toks in reversed(items):
            if acc_tokens + len(toks) <= overlap_budget:
                overlap_items.insert(0, (p_num, txt, toks))
                acc_tokens += len(toks)
            else:
                remaining = overlap_budget - acc_tokens
                if not overlap_items and remaining >= 30:
                    # Si el último párrafo por sí solo rebasa overlap_budget, tomar solo sus últimos tokens
                    sliced_toks = toks[-overlap_budget:]
                    sliced_txt = self.tokenizer.decode(sliced_toks).strip()
                    if sliced_txt:
                        overlap_items.insert(0, (p_num, sliced_txt, sliced_toks))
                break

        return overlap_items

    def chunk_document(
        self,
        doc_name: str,
        pages_content: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not pages_content:
            return []

        categoria = metadata.get("categoria", "general")
        subcategoria = metadata.get("subcategoria", "")
        carrera = metadata.get("carrera", "GENERAL_FI")
        periodo = metadata.get("periodo", "VIGENTE")
        clean_id = metadata.get("clean_id") or f"{carrera.lower()}_{clean_filename(doc_name)}".lower()[:60]

        # Presupuesto de tokens reservado para la cabecera [DOCUMENTO: ... | PÁG: ...]
        sample_header = self._build_header(doc_name, categoria, 999, 999, "Artículo 999 Bis")
        header_overhead = len(self.tokenizer.encode(sample_header)) + 4
        body_target = max(200, min(self.target_tokens, self.max_tokens - header_overhead))
        body_max = max(body_target, self.max_tokens - header_overhead)
        step = max(100, body_target - self.overlap_tokens)

        # 1. Descomponer páginas en pasajes atómicos <= body_target tokens
        passages: List[Tuple[int, str, List[int]]] = []
        for p in pages_content:
            p_num = p["page_number"]
            txt = p["text"]
            paras = [x.strip() for x in re.split(r"\n+", txt) if x.strip()]
            for para in paras:
                p_tokens = self.tokenizer.encode(para)
                if len(p_tokens) > body_target:
                    start = 0
                    while start < len(p_tokens):
                        sub_toks = p_tokens[start : start + body_target]
                        sub_txt = self.tokenizer.decode(sub_toks).strip()
                        if sub_txt:
                            passages.append((p_num, sub_txt, sub_toks))
                        if start + body_target >= len(p_tokens):
                            break
                        start += step
                else:
                    passages.append((p_num, para, p_tokens))

        if not passages:
            return []

        # 2. Agrupar pasajes respetando estrictamente body_target y body_max
        raw_Verify_groups: List[Dict[str, Any]] = []
        curr_items: List[Tuple[int, str, List[int]]] = []
        curr_tok_count = 0
        last_known_article = ""

        def flush_current(items: List[Tuple[int, str, List[int]]], inherited_article: str) -> Tuple[Dict[str, Any], str]:
            body = "\n\n".join(x[1] for x in items)
            matches = _ARTICULO_REGEX.findall(body)
            # Usar el primer artículo explícito del bloque o heredar el vigente
            art_str = matches[0] if matches else inherited_article
            # El último artículo mencionado en este bloque queda activo para el siguiente
            next_inherited = matches[-1] if matches else inherited_article
            return {
                "items": list(items),
                "body": body,
                "start_p": items[0][0],
                "end_p": items[-1][0],
                "articulo": art_str,
            }, next_inherited

        for p_num, text_block, tok_list in passages:
            # +2 tokens aproximados por el separador "\n\n"
            sep_tokens = 2 if curr_items else 0
            if curr_items and (curr_tok_count + sep_tokens + len(tok_list) > body_target):
                group, last_known_article = flush_current(curr_items, last_known_article)
                raw_Verify_groups.append(group)

                # Calcular overlap acotado en tokens
                overlap_items = self._compute_overlap(curr_items, self.overlap_tokens)
                overlap_tok_count = sum(len(x[2]) for x in overlap_items) + max(0, (len(overlap_items) - 1) * 2)

                # Si el overlap + el nuevo bloque exceden body_target, reducir o descartar el overlap
                if overlap_items and (overlap_tok_count + 2 + len(tok_list) > body_target):
                    allowed_overlap = max(0, body_target - len(tok_list) - 2)
                    overlap_items = self._compute_overlap(curr_items, allowed_overlap)
                    overlap_tok_count = sum(len(x[2]) for x in overlap_items) + max(0, (len(overlap_items) - 1) * 2)

                curr_items = overlap_items
                curr_tok_count = overlap_tok_count

            curr_items.append((p_num, text_block, tok_list))
            curr_tok_count += (2 if len(curr_items) > 1 else 0) + len(tok_list)

        if curr_items:
            group, last_known_article = flush_current(curr_items, last_known_article)
            raw_Verify_groups.append(group)

        # 3. Fusionar el último chunk si quedó huérfano (< min_tokens) y cabe en el penúltimo
        if len(raw_Verify_groups) > 1:
            last_g = raw_Verify_groups[-1]
            prev_g = raw_Verify_groups[-2]
            last_header = self._build_header(doc_name, categoria, last_g["start_p"], last_g["end_p"], last_g["articulo"])
            last_total_toks = len(self.tokenizer.encode(last_header + last_g["body"]))

            if last_total_toks < self.min_tokens:
                # Evitar duplicar los items que ya venían por overlap
                prev_texts_set = { id(x[1]): x[1] for x in prev_g["items"] }
                non_overlap_items = [x for x in last_g["items"] if x not in prev_g["items"]]
                merged_items = prev_g["items"] + non_overlap_items
                merged_body = "\n\n".join(x[1] for x in merged_items)
                merged_header = self._build_header(
                    doc_name, categoria, merged_items[0][0], merged_items[-1][0], prev_g["articulo"]
                )
                if len(self.tokenizer.encode(merged_header + merged_body)) <= self.max_tokens:
                    prev_g["items"] = merged_items
                    prev_g["body"] = merged_body
                    prev_g["end_p"] = merged_items[-1][0]
                    raw_Verify_groups.pop()

        # 4. Construir la lista final de chunks con IDs y hashes deterministas
        chunks: List[Dict[str, Any]] = []
        for idx, g in enumerate(raw_Verify_groups, start=1):
            header = self._build_header(doc_name, categoria, g["start_p"], g["end_p"], g["articulo"])
            full_text = header + g["body"]
            full_tokens = self.tokenizer.encode(full_text)

            chunk_id = f"{clean_id}_c{idx:03d}"
            content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

            chunks.append({
                "chunk_id": chunk_id,
                "content_hash": content_hash,
                "text": full_text,
                "raw_text": g["body"],
                "token_count": len(full_tokens),
                "documento": doc_name,
                "categoria": categoria,
                "subcategoria": subcategoria,
                "carrera": carrera,
                "periodo": periodo,
                "articulo": g["articulo"],
                "pagina_inicio": g["start_p"],
                "pagina_fin": g["end_p"],
            })

        return chunks
