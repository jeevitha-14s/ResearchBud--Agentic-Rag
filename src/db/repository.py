import sqlite3
from datetime import UTC, datetime

from src.models.paper import Chunk, Paper, PaperMetadata


def _row_to_paper(row: sqlite3.Row) -> Paper:
    return Paper(
        id=row["id"],
        arxiv_id=row["arxiv_id"],
        title=row["title"],
        authors=row["authors"].split("|"),
        abstract=row["abstract"],
        categories=row["categories"].split("|"),
        published_date=row["published_date"],
        pdf_url=row["pdf_url"],
        pdf_path=row["pdf_path"],
        ingested_at=row["ingested_at"],
    )


def _row_to_chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        id=row["id"],
        paper_id=row["paper_id"],
        chunk_index=row["chunk_index"],
        text=row["text"],
        char_start=row["char_start"],
        char_end=row["char_end"],
    )


class PaperRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_metadata(self, metadata: PaperMetadata) -> Paper:
        self._conn.execute(
            """
            INSERT INTO papers
                (arxiv_id, title, authors, abstract, categories, published_date, pdf_url)
            VALUES
                (:arxiv_id, :title, :authors, :abstract, :categories, :published_date, :pdf_url)
            ON CONFLICT (arxiv_id) DO UPDATE SET
                title = excluded.title,
                authors = excluded.authors,
                abstract = excluded.abstract,
                categories = excluded.categories,
                published_date = excluded.published_date,
                pdf_url = excluded.pdf_url
            """,
            {
                "arxiv_id": metadata.arxiv_id,
                "title": metadata.title,
                "authors": "|".join(metadata.authors),
                "abstract": metadata.abstract,
                "categories": "|".join(metadata.categories),
                "published_date": metadata.published_date,
                "pdf_url": metadata.pdf_url,
            },
        )
        paper = self.get_by_arxiv_id(metadata.arxiv_id)
        assert paper is not None
        return paper

    def get_by_arxiv_id(self, arxiv_id: str) -> Paper | None:
        row = self._conn.execute("SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)).fetchone()
        return _row_to_paper(row) if row else None

    def get_by_id(self, paper_id: int) -> Paper | None:
        row = self._conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return _row_to_paper(row) if row else None

    def mark_ingested(self, paper_id: int, pdf_path: str) -> None:
        self._conn.execute(
            "UPDATE papers SET pdf_path = ?, ingested_at = ? WHERE id = ?",
            (pdf_path, datetime.now(UTC).isoformat(), paper_id),
        )

    def list_papers(self) -> list[Paper]:
        rows = self._conn.execute("SELECT * FROM papers ORDER BY id").fetchall()
        return [_row_to_paper(row) for row in rows]

    def is_fully_ingested(self, arxiv_id: str) -> bool:
        row = self._conn.execute(
            "SELECT ingested_at FROM papers WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        return row is not None and row["ingested_at"] is not None


class ChunkRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def replace_chunks(self, paper_id: int, chunks: list[tuple[str, int, int]]) -> None:
        self._conn.execute("DELETE FROM chunks WHERE paper_id = ?", (paper_id,))
        rows = [
            (paper_id, index, text, char_start, char_end)
            for index, (text, char_start, char_end) in enumerate(chunks)
        ]
        self._conn.executemany(
            """
            INSERT INTO chunks (paper_id, chunk_index, text, char_start, char_end)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

    def get_by_paper(self, paper_id: int) -> list[Chunk]:
        rows = self._conn.execute(
            "SELECT * FROM chunks WHERE paper_id = ? ORDER BY chunk_index", (paper_id,)
        ).fetchall()
        return [_row_to_chunk(row) for row in rows]

    def get_by_id(self, chunk_id: int) -> Chunk | None:
        row = self._conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        return _row_to_chunk(row) if row else None

    def get_all(self) -> list[Chunk]:
        rows = self._conn.execute("SELECT * FROM chunks ORDER BY id").fetchall()
        return [_row_to_chunk(row) for row in rows]
