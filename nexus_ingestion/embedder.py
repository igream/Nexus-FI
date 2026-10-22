import os
import random
import time
from typing import List
import requests

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class TextEmbedder:
    """
    Generador de embeddings vectoriales mediante OpenAI text-embedding-3-small (1536d).
    Incluye connection pooling (requests.Session) y backoff exponencial con jitter
    para resiliencia en entornos cloud ante límites de tasa (429) y errores 5xx.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.dimensions = dimensions
        self.api_url = "https://api.openai.com/v1/embeddings"
        self.session = requests.Session()

    def _validate_api_key(self):
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY no configurada. Define la variable de entorno "
                "en el archivo .env o mediante AWS Secrets Manager."
            )

    def embed_texts(self, texts: List[str], batch_size: int = 128) -> List[List[float]]:
        """Genera embeddings en lotes reutilizando conexiones TLS y con reintentos resilientes."""
        if not texts:
            return []

        self._validate_api_key()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        all_embeddings: List[List[float]] = []
        max_retries = 5

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {
                "input": batch,
                "model": self.model,
            }

            for attempt in range(max_retries):
                try:
                    resp = self.session.post(
                        self.api_url,
                        headers=headers,
                        json=payload,
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        # Ordenar por index para garantizar alineación exacta con el lote de entrada
                        sorted_items = sorted(data["data"], key=lambda x: x["index"])
                        batch_vectors = [item["embedding"] for item in sorted_items]
                        all_embeddings.extend(batch_vectors)
                        break
                    elif resp.status_code == 401:
                        raise ValueError("Error de autenticación (401): OPENAI_API_KEY inválida o revocada.")
                    elif resp.status_code in _RETRYABLE_STATUS_CODES:
                        if attempt == max_retries - 1:
                            raise RuntimeError(
                                f"Error persistente OpenAI API ({resp.status_code}) tras {max_retries} intentos."
                            )
                        retry_after = resp.headers.get("Retry-After")
                        base_wait = float(retry_after) if (retry_after and retry_after.isdigit()) else (2 ** attempt) * 1.5
                        wait_time = base_wait + random.uniform(0.1, 1.0)
                        print(f"  [OpenAI HTTP {resp.status_code}] Reintentando en {wait_time:.1f}s (intento {attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                    else:
                        raise RuntimeError(f"Error OpenAI API ({resp.status_code}): {resp.text[:300]}")
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        raise RuntimeError(f"Fallo de red con OpenAI API tras {max_retries} intentos: {e}")
                    wait_time = (2 ** attempt) + random.uniform(0.1, 0.8)
                    time.sleep(wait_time)

        return all_embeddings

    def embed_query(self, query: str) -> List[float]:
        """Genera el vector de embedding para una consulta de usuario en tiempo real."""
        if not query or not query.strip():
            raise ValueError("La consulta no puede estar vacía.")
        return self.embed_texts([query.strip()], batch_size=1)[0]
