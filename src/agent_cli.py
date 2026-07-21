import argparse

from src.agents.graph import build_graph, initial_state
from src.config import settings
from src.services.bm25_index import Bm25Index
from src.services.embeddings import EmbeddingModel
from src.services.llm import get_llm_client
from src.services.vector_index import VectorIndex


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a query through the agentic RAG graph.")
    parser.add_argument("query")
    args = parser.parse_args()

    bm25_index = Bm25Index.load(settings.bm25_index_path)
    vector_index = VectorIndex()
    embedder = EmbeddingModel()
    llm_client = get_llm_client()

    graph = build_graph(bm25_index, vector_index, embedder, llm_client)
    result = graph.invoke(initial_state(args.query))

    print("--- Trace ---")
    for step in result["trace"]:
        print(f"  {step}")
    print("\n--- Answer ---")
    print(result["answer"])


if __name__ == "__main__":
    main()
