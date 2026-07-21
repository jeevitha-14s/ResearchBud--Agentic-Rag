import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from api_client import ApiError, get_papers, post_ingest, post_reindex  # noqa: E402

st.set_page_config(page_title="Upload / Status — arXiv Paper Curator", page_icon="📊")
st.title("📊 Upload / Status")

st.markdown(
    "Ingestion is arXiv-query-driven, not file-upload — enter an arXiv "
    "search query (e.g. `cat:cs.AI`) to add matching papers to the corpus."
)

st.subheader("Ingest new papers")
with st.form("ingest_form"):
    query = st.text_input("arXiv query", value="cat:cs.AI")
    max_results = st.number_input("Max results", min_value=1, max_value=100, value=10)
    force = st.checkbox("Force re-ingest already-ingested papers")
    submitted = st.form_submit_button("Ingest")

if submitted:
    try:
        with st.spinner("Ingesting — this can take a while for larger queries..."):
            result = post_ingest(query, int(max_results), force)
    except ApiError as exc:
        st.error(str(exc))
    else:
        st.success(f"Ingested {result['ingested']}, skipped {result['skipped']}.")

st.divider()

st.subheader("Rebuild search indices")
st.markdown("Run this after ingesting new papers so they become searchable.")
if st.button("Rebuild BM25 + vector indices"):
    try:
        with st.spinner("Rebuilding indices..."):
            result = post_reindex()
    except ApiError as exc:
        st.error(str(exc))
    else:
        st.success(f"Indexed {result['chunks_indexed']} chunks.")

st.divider()

st.subheader("Ingested papers")
try:
    papers = get_papers()
except ApiError as exc:
    st.error(str(exc))
else:
    if papers:
        st.dataframe(papers, use_container_width=True)
    else:
        st.info("No papers ingested yet.")
