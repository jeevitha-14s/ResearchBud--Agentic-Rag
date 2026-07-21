import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402
from api_client import ApiError, get_health  # noqa: E402

st.set_page_config(page_title="arXiv Paper Curator", page_icon="📄")

st.title("📄 arXiv Paper Curator")
st.markdown(
    """
An agentic RAG system over arXiv papers — hybrid BM25 + vector search,
guarded and self-correcting retrieval, cited answers.

Use the sidebar to navigate:
- **Chat** — ask questions about the ingested papers, with an inline,
  expandable reasoning trace per answer.
- **Upload / Status** — ingest new papers by arXiv query, rebuild the
  search indices, and see what's currently in the corpus.
"""
)

st.divider()

try:
    health = get_health()
    st.success(f"Backend reachable — status: {health.get('status', 'unknown')}")
except ApiError as exc:
    st.error(str(exc))
