from pathlib import Path

import httpx
import pdfplumber

from src.services.retry import with_retry


def download_pdf(pdf_url: str, dest_path: str, max_retries: int = 3) -> str:
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

    @with_retry(max_retries=max_retries)
    def _download() -> None:
        with httpx.stream("GET", pdf_url, timeout=60, follow_redirects=True) as response:
            response.raise_for_status()
            with Path(dest_path).open("wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)

    _download()
    return dest_path


def extract_text(pdf_path: str) -> str:
    pages_text: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
    return "\n\n".join(pages_text)
