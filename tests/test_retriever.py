from app.rag.retriever import DatasheetRetriever
from app.services.diagnostic_engine import DEFAULT_KNOWLEDGE

def test_trigger_query_retrieves_trigger_section():
    result = DatasheetRetriever.from_markdown(DEFAULT_KNOWLEDGE).search("minimum trigger pulse 10 microseconds", 1)[0]
    assert result.chunk.section == "Trigger timing"
    assert result.score > 0
