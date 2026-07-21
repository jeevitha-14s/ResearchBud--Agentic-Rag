import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from api_client import ApiError, post_chat  # noqa: E402

st.set_page_config(page_title="Chat — arXiv Paper Curator", page_icon="💬")
st.title("💬 Chat")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for turn in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(turn["query"])
    with st.chat_message("assistant"):
        if turn["rejected"]:
            st.warning(turn["answer"])
        else:
            st.markdown(turn["answer"])
        with st.expander("🔍 Reasoning trace"):
            for step in turn["trace"]:
                st.text(step)

query = st.chat_input("Ask something about the ingested papers...")
if query:
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                result = post_chat(query)
        except ApiError as exc:
            st.error(str(exc))
        else:
            if result["rejected"]:
                st.warning(result["answer"])
            else:
                st.markdown(result["answer"])
            with st.expander("🔍 Reasoning trace"):
                for step in result["trace"]:
                    st.text(step)

            st.session_state.chat_history.append(
                {
                    "query": query,
                    "answer": result["answer"],
                    "rejected": result["rejected"],
                    "trace": result["trace"],
                }
            )
