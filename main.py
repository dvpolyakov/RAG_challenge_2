import click
from pathlib import Path
import re
import json
from src.pipeline import Pipeline, configs, preprocess_configs
from src.text_processing.text_splitter import TextSplitter

@click.group()
def cli():
    """Pipeline CLI for persona transcripts and questions (PDF path kept for legacy)."""
    pass

# @cli.command()
# def download_models():
#     """Download required docling models."""
#     click.echo("Downloading docling models...")
#     Pipeline.download_docling_models()

# @cli.command()
# @click.option('--parallel/--sequential', default=True, help='Run parsing in parallel or sequential mode')
# @click.option('--chunk-size', default=2, help='Number of PDFs to process in each worker')
# @click.option('--max-workers', default=10, help='Number of parallel worker processes')
# def parse_pdfs(parallel, chunk_size, max_workers):
#     """Parse PDF reports with optional parallel processing."""
#     root_path = Path.cwd()
#     pipeline = Pipeline(root_path)
#     
#     click.echo(f"Parsing PDFs (parallel={parallel}, chunk_size={chunk_size}, max_workers={max_workers})")
#     pipeline.parse_pdf_reports(parallel=parallel, chunk_size=chunk_size, max_workers=max_workers)

# @cli.command()
# @click.option('--max-workers', default=10, help='Number of workers for table serialization')
# def serialize_tables(max_workers):
#     """Serialize tables in parsed reports using parallel threading."""
#     root_path = Path.cwd()
#     pipeline = Pipeline(root_path)
#     
#     click.echo(f"Serializing tables (max_workers={max_workers})...")
#     pipeline.serialize_tables(max_workers=max_workers)

# @cli.command()
# @click.option('--config', type=click.Choice(['ser_tab', 'no_ser_tab']), default='no_ser_tab', help='Configuration preset to use')
# def process_reports(config):
#     """Process parsed reports through the pipeline stages."""
#     root_path = Path.cwd()
#     run_config = preprocess_configs[config]
#     pipeline = Pipeline(root_path, run_config=run_config)
#     
#     click.echo(f"Processing parsed reports (config={config})...")
#     pipeline.process_parsed_reports()

@cli.command()
@click.option('--config', type=click.Choice(['base', 'pdr', 'max', 'max_no_ser_tab', 'max_nst_o3m', 'max_st_o3m', 'ibm_llama70b', 'ibm_llama8b', 'gemini_thinking']), default='base', help='Configuration preset to use')
def process_questions(config):
    """Process questions using the pipeline."""
    root_path = Path.cwd()
    run_config = configs[config]
    pipeline = Pipeline(root_path, run_config=run_config)
    
    click.echo(f"Processing questions (config={config})...")
    pipeline.process_questions()

@cli.command(name='transcripts-to-chunked')
@click.option('--company-name', required=True, help='Persona display name (used for retrieval).')
@click.option('--sha1-name', default='persona_interviews', show_default=True, help='Stable identifier; also output JSON filename.')
@click.option('--input-glob', default='transcript*.txt', show_default=True, help='Glob for transcript .txt files in current directory.')
@click.option('--chunk-size', default=600, show_default=True, help='Chunk size for splitting pages.')
@click.option('--chunk-overlap', default=120, show_default=True, help='Chunk overlap for splitting pages.')
def transcripts_to_chunked(company_name, sha1_name, input_glob, chunk_size, chunk_overlap):
    """Convert transcript .txt files (MM:SS Speaker: text) into chunked_reports JSON."""
    root_path = Path.cwd()
    txt_paths = sorted(root_path.glob(input_glob))
    if not txt_paths:
        click.echo(f"No transcripts found matching pattern: {input_glob}")
        return

    ts_re = re.compile(r'^\s*\d{2}:\d{2}\s')

    def parse_txt_to_pages(txt: str):
        segments = []
        buf = []
        for line in txt.splitlines():
            if ts_re.match(line):
                if buf:
                    segments.append("\n".join(buf).strip())
                    buf = []
                buf.append(line.strip())
            else:
                if buf or line.strip():
                    buf.append(line.strip())
        if buf:
            segments.append("\n".join(buf).strip())
        return [{"page": i + 1, "text": seg} for i, seg in enumerate(segments)]

    pages = []
    for tp in txt_paths:
        txt = tp.read_text(encoding='utf-8')
        pages.extend(parse_txt_to_pages(txt))

    splitter = TextSplitter()
    chunks = []
    for pg in pages:
        for ch in splitter._split_page(pg, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            chunks.append(ch)

    doc = {
        "metainfo": {"company_name": company_name, "sha1_name": sha1_name},
        "content": {"pages": pages, "chunks": chunks}
    }

    out_dir = root_path / 'databases' / 'chunked_reports'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sha1_name}.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
    click.echo(f"Saved chunked report: {out_path}")

@cli.command(name='create-vector-dbs')
def create_vector_dbs_cmd():
    """Create vector DBs from existing chunked_reports JSONs."""
    root_path = Path.cwd()
    pipeline = Pipeline(root_path)
    click.echo("Creating vector databases from chunked reports...")
    pipeline.create_vector_dbs()

if __name__ == '__main__':
    cli()