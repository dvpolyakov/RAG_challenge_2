import argparse
import json
import re
from pathlib import Path
from typing import List, Dict

from src.text_processing.text_splitter import TextSplitter


def parse_txt_to_pages(text: str) -> List[Dict[str, str]]:
    """Split raw transcript text by MM:SS timecodes into page dicts (1-based)."""
    timecode_pattern = re.compile(r"^\s*\d{2}:\d{2}\s", re.MULTILINE)
    segments: List[str] = []
    buffer: List[str] = []

    for line in text.splitlines():
        if timecode_pattern.match(line):
            if buffer:
                segments.append("\n".join(buffer).strip())
                buffer = []
            buffer.append(line.strip())
        else:
            if buffer or line.strip():
                buffer.append(line.strip())

    if buffer:
        segments.append("\n".join(buffer).strip())

    return [{"page": index + 1, "text": segment} for index, segment in enumerate(segments)]


def build_chunked_document(
    pages: List[Dict[str, str]],
    company_name: str,
    sha1_name: str,
    chunk_size: int,
    chunk_overlap: int,
) -> Dict:
    splitter = TextSplitter()
    chunks: List[Dict] = []

    for page in pages:
        page_chunks = splitter._split_page(page, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks.extend(page_chunks)

    document = {
        "metainfo": {"company_name": company_name, "sha1_name": sha1_name},
        "content": {"pages": pages, "chunks": chunks},
    }
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert transcript .txt files to chunked_reports JSON.")
    parser.add_argument("--root", default="data/persona_set", help="Root directory containing transcripts and output dirs.")
    parser.add_argument("--input-glob", default="transcript*.txt", help="Glob pattern to match transcript files.")
    parser.add_argument("--company-name", required=True, help="Persona display name (used for retrieval).")
    parser.add_argument("--sha1-name", default="persona_interviews", help="Stable identifier; output JSON filename stem.")
    parser.add_argument("--chunk-size", type=int, default=600, help="Chunk size for splitting pages.")
    parser.add_argument("--chunk-overlap", type=int, default=120, help="Chunk overlap for splitting pages.")
    parser.add_argument("--output-dir", default=None, help="Output directory for chunked JSON (defaults to <root>/databases/chunked_reports).")
    parser.add_argument("--output-filename", default=None, help="Output filename (defaults to <sha1-name>.json).")

    args = parser.parse_args()

    root_path = Path(args.root)
    transcripts = sorted(root_path.glob(args.input_glob))
    if not transcripts:
        raise FileNotFoundError(f"No transcripts found in '{root_path}' matching '{args.input_glob}'")

    pages: List[Dict[str, str]] = []
    for transcript_path in transcripts:
        content = transcript_path.read_text(encoding="utf-8")
        pages.extend(parse_txt_to_pages(content))

    if not pages:
        raise ValueError("No pages parsed from transcripts. Check input format (MM:SS Speaker: text).")

    doc = build_chunked_document(
        pages=pages,
        company_name=args.company_name,
        sha1_name=args.sha1_name,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    output_dir = Path(args.output_dir) if args.output_dir else (root_path / "databases" / "chunked_reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = args.output_filename or f"{args.sha1_name}.json"
    output_path = output_dir / output_filename

    output_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved chunked report: {output_path}")


if __name__ == "__main__":
    main()


