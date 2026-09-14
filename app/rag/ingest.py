from dataclasses import dataclass
from pathlib import Path
import json
import re

from pypdf import PdfReader


@dataclass(frozen=True)
class PdfChunk:
    chunk_id: str
    source: str
    page: int
    text: str


def clean_text(text: str) -> str:
    """
    Normalize whitespace while keeping extracted PDF text readable.
    """
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_chunks(
    text: str,
    max_chars: int = 900,
) -> list[str]:
    """
    Split a page into small, meaningful chunks.
    """
    paragraphs = [
        part.strip()
        for part in re.split(r"\n\s*\n", text)
        if part.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            sentences = re.split(
                r"(?<=[.!?])\s+",
                paragraph,
            )
        else:
            sentences = [paragraph]

        for sentence in sentences:
            candidate = (
                sentence
                if not current
                else f"{current}\n{sentence}"
            )

            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())

                current = sentence

    if current:
        chunks.append(current.strip())

    return chunks


def ingest_pdf(
    pdf_path: str | Path,
) -> list[PdfChunk]:
    pdf_path = Path(pdf_path)

    reader = PdfReader(str(pdf_path))

    all_chunks = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        raw_text = page.extract_text() or ""
        cleaned = clean_text(raw_text)

        if not cleaned:
            continue

        page_chunks = split_into_chunks(cleaned)

        for chunk_number, chunk_text in enumerate(
            page_chunks,
            start=1,
        ):
            chunk_id = (
                f"{pdf_path.stem}"
                f"_p{page_number}"
                f"_c{chunk_number}"
            )

            all_chunks.append(
                PdfChunk(
                    chunk_id=chunk_id,
                    source=pdf_path.name,
                    page=page_number,
                    text=chunk_text,
                )
            )

    return all_chunks


def save_chunks(
    chunks: list[PdfChunk],
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)

    data = [
        {
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "page": chunk.page,
            "text": chunk.text,
        }
        for chunk in chunks
    ]

    output_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]

    pdf_path = (
        root
        / "data"
        / "datasheets"
        / "hc_sr04_original.pdf"
    )

    output_path = (
        root
        / "data"
        / "datasheets"
        / "hc_sr04_chunks.json"
    )

    chunks = ingest_pdf(pdf_path)

    save_chunks(
        chunks,
        output_path,
    )

    print(
        f"Created {len(chunks)} chunks "
        f"from {pdf_path.name}"
    )

    print()

    for chunk in chunks:
        lower_text = chunk.text.lower()

        if (
            "10us" in lower_text
            or "10 us" in lower_text
            or "trigger" in lower_text
            or "60ms" in lower_text
            or "60 ms" in lower_text
        ):
            print(
                f"[{chunk.chunk_id}] "
                f"{chunk.source} "
                f"page {chunk.page}"
            )
            print(chunk.text)
            print("-" * 80)