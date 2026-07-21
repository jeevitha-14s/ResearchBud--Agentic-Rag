from unittest.mock import MagicMock, patch

from src.services.arxiv_client import ArxivClient

SAMPLE_ATOM_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2101.00001v1</id>
    <title>  A Great Paper
      About Testing  </title>
    <summary>  This is the abstract.
      It spans lines.  </summary>
    <published>2021-01-01T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <link href="http://arxiv.org/abs/2101.00001v1" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2101.00001v1" rel="related"
      type="application/pdf"/>
  </entry>
</feed>
"""


@patch("src.services.arxiv_client.time.sleep")
@patch("src.services.arxiv_client.httpx.get")
def test_search_parses_entry_fields(mock_get: MagicMock, mock_sleep: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.text = SAMPLE_ATOM_RESPONSE
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    client = ArxivClient(request_delay_seconds=0)
    results = client.search("cat:cs.AI", max_results=1)

    assert len(results) == 1
    paper = results[0]
    assert paper.arxiv_id == "2101.00001v1"
    assert paper.title == "A Great Paper About Testing"
    assert paper.abstract == "This is the abstract. It spans lines."
    assert paper.authors == ["Ada Lovelace", "Alan Turing"]
    assert paper.categories == ["cs.AI", "cs.LG"]
    assert paper.pdf_url == "http://arxiv.org/pdf/2101.00001v1"
    assert paper.published_date == "2021-01-01T00:00:00Z"


@patch("src.services.arxiv_client.time.sleep")
@patch("src.services.arxiv_client.httpx.get")
def test_search_retries_on_failure_then_succeeds(
    mock_get: MagicMock, mock_sleep: MagicMock
) -> None:
    mock_response = MagicMock()
    mock_response.text = SAMPLE_ATOM_RESPONSE
    mock_response.raise_for_status.return_value = None
    mock_get.side_effect = [ConnectionError("boom"), mock_response]

    client = ArxivClient(max_retries=2, request_delay_seconds=0)
    results = client.search("cat:cs.AI", max_results=1)

    assert len(results) == 1
    assert mock_get.call_count == 2
