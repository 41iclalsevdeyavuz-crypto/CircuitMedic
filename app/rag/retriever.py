from dataclasses import dataclass
from pathlib import Path
import json

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source: str
    page: int | None
    section: str | None
    text: str


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float


def load_json_chunks(path: str | Path) -> list[Chunk]:
    """
    Load chunks previously extracted from a PDF by ingest.py.
    """
    path = Path(path)

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    chunks = []

    for item in data:
        chunks.append(
            Chunk(
                chunk_id=item["chunk_id"],
                source=item["source"],
                page=item.get("page"),
                section=None,
                text=item["text"],
            )
        )

    if not chunks:
        raise ValueError(
            f"No chunks found in {path}"
        )

    return chunks


def load_markdown_chunks(path: str | Path) -> list[Chunk]:
    """
    Load simple level-2 markdown sections as retrievable chunks.
    """
    path = Path(path)

    text = path.read_text(encoding="utf-8")

    parts = text.split("## ")

    chunks = []

    for index, part in enumerate(parts[1:], start=1):
        heading, _, body = part.partition("\n")

        body = body.strip()

        if not body:
            continue

        chunks.append(
            Chunk(
                chunk_id=f"{path.stem}_c{index}",
                source=path.name,
                page=None,
                section=heading.strip(),
                text=body,
            )
        )

    if not chunks:
        raise ValueError(
            f"No markdown chunks found in {path}"
        )

    return chunks


class DatasheetRetriever:
    """
    Small deterministic TF-IDF retriever.

    Supports:
    - JSON chunks extracted from the real HC-SR04 PDF
    - Markdown chunks for secondary references such as Arduino API notes
    """

    def __init__(self, chunks: list[Chunk]):
        if not chunks:
            raise ValueError(
                "At least one datasheet chunk is required"
            )

        self.chunks = chunks

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
        )

        self.matrix = self.vectorizer.fit_transform(
            chunk.text
            for chunk in chunks
        )

    @classmethod
    def from_json(
        cls,
        path: str | Path,
    ) -> "DatasheetRetriever":
        return cls(
            load_json_chunks(path)
        )

    @classmethod
    def from_markdown(
        cls,
        path: str | Path,
    ) -> "DatasheetRetriever":
        return cls(
            load_markdown_chunks(path)
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[SearchResult]:
        if not query.strip():
            return []

        query_vector = self.vectorizer.transform(
            [query]
        )

        scores = cosine_similarity(
            query_vector,
            self.matrix,
        ).ravel()

        order = scores.argsort()[::-1][
            :max(1, top_k)
        ]

        return [
            SearchResult(
                chunk=self.chunks[index],
                score=float(scores[index]),
            )
            for index in order
        ]