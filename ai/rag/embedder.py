"""Sentence embedding using BGE (English). Arabic is intentionally NOT
supported for now, so we use BAAI/bge-base-en-v1.5 (768-dim).

BGE retrieval works best when queries are prefixed with an instruction.
The model is loaded lazily so importing this module is cheap.
"""
from ai.config import settings

_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy

            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return self._ensure_model().get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        model = self._ensure_model()
        vec = model.encode(
            _QUERY_INSTRUCTION + text, normalize_embeddings=True, show_progress_bar=False
        )
        return vec.tolist()
