from typing import Protocol

from sentence_transformers import SentenceTransformer

from src.config import settings


class Embedder(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingModel:
    def __init__(self, model_name: str | None = None) -> None:
        self._model = SentenceTransformer(model_name or settings.embedding_model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
