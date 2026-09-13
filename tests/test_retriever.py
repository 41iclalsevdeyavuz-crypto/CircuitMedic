from app.rag.retriever import DatasheetRetriever
from app.services.diagnostic_engine import DEFAULT_KNOWLEDGE


def test_trigger_query_retrieves_trigger_chunk():
    result = DatasheetRetriever.from_json(
        DEFAULT_KNOWLEDGE
    ).search(
        "minimum trigger pulse 10 microseconds",
        1,
    )[0]

    assert result.chunk.source == "hc_sr04_original.pdf"
    assert result.chunk.page in (1, 2)
    assert "trigger" in result.chunk.text.lower()
    assert result.score > 0