from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.config import settings
from src.models.paper import Chunk
from src.services.embeddings import Embedder


class VectorIndex:
    def __init__(self, client: QdrantClient | None = None) -> None:
        self._client = client or QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        self._collection = settings.qdrant_collection_name

    def ensure_collection(self, dim: int) -> None:
        if self._client.collection_exists(self._collection):
            info = self._client.get_collection(self._collection)
            existing_dim = info.config.params.vectors.size  # type: ignore[union-attr]
            if existing_dim != dim:
                raise ValueError(
                    f"Qdrant collection '{self._collection}' has vector dim "
                    f"{existing_dim}, but embedding model produces dim {dim}. "
                    "Delete the collection or use a matching model."
                )
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )

    def upsert_chunks(self, chunks: list[Chunk], embedder: Embedder) -> None:
        if not chunks:
            return
        vectors = embedder.embed_texts([chunk.text for chunk in chunks])
        points = [
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload={"paper_id": chunk.paper_id, "chunk_index": chunk.chunk_index},
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
            if chunk.id is not None
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def search(self, query_vector: list[float], top_k: int) -> list[tuple[int, float]]:
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=top_k,
        ).points
        return [(int(point.id), point.score) for point in results]
