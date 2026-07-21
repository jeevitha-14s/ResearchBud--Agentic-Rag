import argparse

from src.config import settings
from src.models.search import SearchResult
from src.services.bm25_index import Bm25Index
from src.services.embeddings import EmbeddingModel
from src.services.search import bm25_search, hybrid_search, vector_search
from src.services.vector_index import VectorIndex


def _print_results(label: str, results: list[SearchResult]) -> None:
    print(f"\n--- {label} ---")
    if not results:
        print("(no results)")
        return
    for rank, result in enumerate(results, start=1):
        preview = result.text[:100].replace("\n", " ")
        print(f"{rank}. [{result.score:.4f}] {result.title} :: {preview}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare BM25, vector, and hybrid search.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=settings.search_default_top_k)
    args = parser.parse_args()

    bm25_index = Bm25Index.load(settings.bm25_index_path)
    vector_index = VectorIndex()
    embedder = EmbeddingModel()

    _print_results("BM25", bm25_search(bm25_index, args.query, args.top_k))
    _print_results("Vector", vector_search(vector_index, embedder, args.query, args.top_k))
    _print_results(
        "Hybrid (RRF)", hybrid_search(bm25_index, vector_index, embedder, args.query, args.top_k)
    )


if __name__ == "__main__":
    main()
