from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


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
    path = Path(path)

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    chunks = [
        Chunk(
            chunk_id=item["chunk_id"],
            source=item["source"],
            page=item.get("page"),
            section=None,
            text=item["text"],
        )
        for item in data
    ]

    if not chunks:
        raise ValueError(
            f"No chunks found in {path}"
        )

    return chunks


def load_markdown_chunks(path: str | Path) -> list[Chunk]:
    path = Path(path)

    text = path.read_text(encoding="utf-8")

    parts = text.split("## ")

    chunks = []

    for index, part in enumerate(
        parts[1:],
        start=1,
    ):
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


def _chunks_fingerprint(
    chunks: list[Chunk],
) -> str:
    """
    Create a stable fingerprint so cached embeddings
    are regenerated only when source chunks change.
    """
    payload = "\n".join(
        f"{chunk.chunk_id}|{chunk.text}"
        for chunk in chunks
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


class DatasheetRetriever:
    """
    Local semantic retriever using sentence embeddings.

    Document embeddings are cached on disk and reused
    between analyses.
    """

    def __init__(
        self,
        chunks: list[Chunk],
        cache_path: str | Path,
        model_name: str = MODEL_NAME,
    ):
        if not chunks:
            raise ValueError(
                "At least one chunk is required"
            )

        self.chunks = chunks
        self.cache_path = Path(cache_path)
        self.model_name = model_name

        self.model = SentenceTransformer(
            model_name
        )

        self.embeddings = (
            self._load_or_create_embeddings()
        )

    def _load_or_create_embeddings(
        self,
    ) -> np.ndarray:
        fingerprint = _chunks_fingerprint(
            self.chunks
        )

        if self.cache_path.exists():
            cached = np.load(
                self.cache_path,
                allow_pickle=False,
            )

            cached_fingerprint = str(
                cached["fingerprint"].item()
            )

            cached_model = str(
                cached["model_name"].item()
            )

            embeddings = cached["embeddings"]

            if (
                cached_fingerprint == fingerprint
                and cached_model == self.model_name
                and len(embeddings) == len(self.chunks)
            ):
                return embeddings

        texts = [
            chunk.text
            for chunk in self.chunks
        ]

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        self.cache_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        np.savez_compressed(
            self.cache_path,
            embeddings=embeddings,
            fingerprint=np.array(fingerprint),
            model_name=np.array(self.model_name),
        )

        return embeddings

    @classmethod
    def from_json(
        cls,
        path: str | Path,
    ) -> "DatasheetRetriever":
        path = Path(path)

        cache_path = (
            path.parent
            / "embeddings"
            / f"{path.stem}.npz"
        )

        return cls(
            chunks=load_json_chunks(path),
            cache_path=cache_path,
        )

    @classmethod
    def from_markdown(
        cls,
        path: str | Path,
    ) -> "DatasheetRetriever":
        path = Path(path)

        cache_path = (
            path.parent
            / "embeddings"
            / f"{path.stem}.npz"
        )

        return cls(
            chunks=load_markdown_chunks(path),
            cache_path=cache_path,
        )

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.35,
    ) -> list[SearchResult]:
        """
        Semantic search.

        Results below min_score are rejected instead of
        forcing an unrelated chunk to become "evidence".
        """
        if not query.strip():
            return []

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        scores = (
            self.embeddings
            @ query_embedding
        )

        order = scores.argsort()[::-1]

        results = []

        for index in order:
            score = float(scores[index])

            if score < min_score:
                continue

            results.append(
                SearchResult(
                    chunk=self.chunks[index],
                    score=score,
                )
            )

            if len(results) >= top_k:
                break

        return results