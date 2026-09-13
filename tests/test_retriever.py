from app.rag.retriever import DatasheetRetriever
from app.services.diagnostic_engine import DEFAULT_KNOWLEDGE


def test_trigger_query_retrieves_trigger_chunk():
    retriever = DatasheetRetriever.from_json(
        DEFAULT_KNOWLEDGE
    )

    results = retriever.search(
        "How long should the HC-SR04 trigger pulse be?",
        3,
    )

    assert results

    best = results[0]

    assert best.chunk.source == "hc_sr04_original.pdf"
    assert best.chunk.page in (1, 2)
    assert "trigger" in best.chunk.text.lower()
    assert best.score >= 0.35


def test_irrelevant_query_returns_no_evidence():
    retriever = DatasheetRetriever.from_json(
        DEFAULT_KNOWLEDGE
    )

    results = retriever.search(
        "What is the best recipe for chocolate cake?",
        3,
    )

    assert results == []