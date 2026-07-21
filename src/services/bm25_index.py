import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from src.models.paper import Chunk

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


class Bm25Index:
    def __init__(self, bm25: BM25Okapi, chunk_ids: list[int]) -> None:
        self._bm25 = bm25
        self._chunk_ids = chunk_ids

    @classmethod
    def build(cls, chunks: list[Chunk]) -> "Bm25Index":
        tokenized_corpus = [tokenize(chunk.text) for chunk in chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        chunk_ids = [chunk.id for chunk in chunks if chunk.id is not None]
        return cls(bm25, chunk_ids)

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self._chunk_ids, scores, strict=True), key=lambda pair: -pair[1])
        return [(chunk_id, float(score)) for chunk_id, score in ranked[:top_k] if score > 0]

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with Path(path).open("wb") as f:
            pickle.dump({"bm25": self._bm25, "chunk_ids": self._chunk_ids}, f)

    @classmethod
    def load(cls, path: str) -> "Bm25Index":
        with Path(path).open("rb") as f:
            data = pickle.load(f)  # noqa: S301
        return cls(data["bm25"], data["chunk_ids"])
