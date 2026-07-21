import argparse
import logging

from src.config import settings
from src.db.schema import init_db
from src.services.ingestion import ingest_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest papers from arXiv into SQLite.")
    parser.add_argument("--query", required=True, help="arXiv search query, e.g. 'cat:cs.AI'")
    parser.add_argument(
        "--max-results",
        type=int,
        default=settings.arxiv_default_max_results,
        help="Maximum number of papers to fetch",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest papers even if already fully ingested",
    )
    args = parser.parse_args()

    init_db(settings.sqlite_db_path)
    ingested, skipped = ingest_query(args.query, args.max_results, args.force)
    logger.info("Done: %d ingested, %d skipped", ingested, skipped)


if __name__ == "__main__":
    main()
