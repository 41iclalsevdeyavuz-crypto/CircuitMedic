from dataclasses import dataclass
from pathlib import Path
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

@dataclass(frozen=True)
class Chunk:
    source: str
    section: str
    text: str

@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float

def load_markdown_chunks(path: str | Path) -> list[Chunk]:
    path = Path(path)
    parts = re.split(r"^##\s+", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    chunks = []
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        if body.strip():
            chunks.append(Chunk(path.name, heading.strip(), body.strip()))
    if not chunks:
        raise ValueError(f"No level-2 sections found in {path}")
    return chunks

class DatasheetRetriever:
    """Small deterministic retriever suitable for an offline MVP."""
    def __init__(self, chunks: list[Chunk]):
        if not chunks:
            raise ValueError("At least one datasheet chunk is required")
        self.chunks = chunks
        self.vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(f"{c.section} {c.text}" for c in chunks)

    @classmethod
    def from_markdown(cls, path: str | Path) -> "DatasheetRetriever":
        return cls(load_markdown_chunks(path))

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        if not query.strip():
            return []
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix).ravel()
        order = scores.argsort()[::-1][:max(1, top_k)]
        return [SearchResult(self.chunks[i], float(scores[i])) for i in order]
