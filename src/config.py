from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# pydantic-settings' env_file only populates fields declared on Settings below —
# it does not export them into os.environ. Third-party SDKs that read
# credentials directly from the environment (anthropic.Anthropic(),
# openai.OpenAI()) need this explicit load to see ANTHROPIC_API_KEY /
# OPENAI_API_KEY from .env.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    redis_host: str = "localhost"
    redis_port: int = 6379

    arxiv_api_base_url: str = "https://export.arxiv.org/api/query"
    arxiv_default_max_results: int = 10
    arxiv_request_delay_seconds: float = 3.0
    arxiv_max_retries: int = 3

    sqlite_db_path: str = "data/arxiv_rag.db"
    pdf_storage_dir: str = "data/pdfs"

    chunk_size_chars: int = 1500
    chunk_overlap_chars: int = 200

    qdrant_collection_name: str = "arxiv_chunks"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    bm25_index_path: str = "data/bm25_index.pkl"
    rrf_k: int = 60
    search_candidate_pool: int = 20
    search_default_top_k: int = 5

    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5"
    llm_max_retries: int = 3
    max_rewrites: int = 2
    min_relevant_chunks: int = 1
    agent_retrieval_top_k: int = 5

    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    redis_cache_ttl_seconds: int = 3600
    rate_limit_search: str = "30/minute"
    rate_limit_chat: str = "10/minute"
    rate_limit_ingest: str = "5/minute"


settings = Settings()
