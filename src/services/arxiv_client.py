import time
import xml.etree.ElementTree as ET

import httpx

from src.config import settings
from src.models.paper import PaperMetadata
from src.services.retry import with_retry

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _text(element: ET.Element, tag: str) -> str:
    found = element.find(f"{_ATOM_NS}{tag}")
    return (found.text or "").strip() if found is not None else ""


def _parse_entry(entry: ET.Element) -> PaperMetadata:
    raw_id = _text(entry, "id")
    arxiv_id = raw_id.rsplit("/", maxsplit=1)[-1]

    authors = [
        (author.find(f"{_ATOM_NS}name").text or "").strip()  # type: ignore[union-attr]
        for author in entry.findall(f"{_ATOM_NS}author")
    ]
    categories = [
        category.attrib["term"]
        for category in entry.findall(f"{_ATOM_NS}category")
        if "term" in category.attrib
    ]

    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    for link in entry.findall(f"{_ATOM_NS}link"):
        if link.attrib.get("title") == "pdf":
            pdf_url = link.attrib["href"]

    return PaperMetadata(
        arxiv_id=arxiv_id,
        title=" ".join(_text(entry, "title").split()),
        authors=authors,
        abstract=" ".join(_text(entry, "summary").split()),
        categories=categories,
        published_date=_text(entry, "published"),
        pdf_url=pdf_url,
    )


class ArxivClient:
    def __init__(
        self,
        base_url: str | None = None,
        max_retries: int | None = None,
        request_delay_seconds: float | None = None,
    ) -> None:
        self._base_url = base_url or settings.arxiv_api_base_url
        self._max_retries = max_retries or settings.arxiv_max_retries
        self._request_delay_seconds = (
            request_delay_seconds
            if request_delay_seconds is not None
            else settings.arxiv_request_delay_seconds
        )

    def search(self, query: str, max_results: int) -> list[PaperMetadata]:
        response = self._fetch(query, max_results)
        root = ET.fromstring(response)
        return [_parse_entry(entry) for entry in root.findall(f"{_ATOM_NS}entry")]

    def _fetch(self, query: str, max_results: int) -> str:
        @with_retry(max_retries=self._max_retries)
        def _get() -> str:
            response = httpx.get(
                self._base_url,
                params={"search_query": query, "start": 0, "max_results": max_results},
                timeout=30,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.text

        result = _get()
        time.sleep(self._request_delay_seconds)
        return result
