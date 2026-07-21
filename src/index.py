import logging

from src.config import settings
from src.db.connection import get_connection
from src.db.repository import ChunkRepository
from src.services.bm25_index import Bm25Index
from src.services.embeddings import EmbeddingModel
from src.services.vector_index import VectorIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_indices() -> None:
    with get_connection() as conn:
        chunks = ChunkRepository(conn).get_all()

    if not chunks:
        logger.warning("No chunks found in SQLite — run ingestion first.")
        return

    logger.info("Building BM25 index over %d chunks", len(chunks))
    bm25_index = Bm25Index.build(chunks)
    bm25_index.save(settings.bm25_index_path)
    logger.info("BM25 index saved to %s", settings.bm25_index_path)

    logger.info("Loading embedding model %s", settings.embedding_model_name)
    embedder = EmbeddingModel()

    logger.info(
        "Upserting %d chunks into Qdrant collection '%s'",
        len(chunks),
        settings.qdrant_collection_name,
    )
    vector_index = VectorIndex()
    vector_index.ensure_collection(settings.embedding_dim)
    vector_index.upsert_chunks(chunks, embedder)
    logger.info("Done.")


if __name__ == "__main__":
    build_indices()
