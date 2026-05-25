# quip-export

Export Quip documents (threads) to Markdown, DOCX, and PDF.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # if using pip
# or
uv sync --dev                    # if using uv
```

Set your Quip API token:
```bash
export QUIP_TOKEN=your_token_here
```

## Running

```bash
quip-export THREAD_ID                          # all formats to current dir
quip-export THREAD_ID -o ./output -f md -f pdf # specific formats and output dir
python -m quip_export THREAD_ID                # run without installing
```

## Development

```bash
# Tests (always run before committing — sets DYLD_LIBRARY_PATH for WeasyPrint)
make test

# Lint
make lint          # or: .venv/bin/ruff check src tests

# Type check
make typecheck     # or: .venv/bin/mypy src
```

> **macOS note:** WeasyPrint requires `libgobject` from Homebrew (`brew install pango`).
> `make test` sets `DYLD_LIBRARY_PATH=/opt/homebrew/lib` automatically.
> Running `.venv/bin/pytest` directly will fail unless you export that variable first.

## Rules

- Always update tests and docs alongside every code change.
- Never commit `.env` or any file containing a `QUIP_TOKEN`.
- Keep `CLAUDE.md` up to date when adding new commands or changing the API.

## Architecture

```
src/quip_export/
├── cli.py        # typer CLI — entry point
├── client.py     # httpx-based Quip REST API client
├── exporter.py   # orchestrates fetch + write
└── formats/
    ├── markdown.py  # markdownify-based HTML→MD
    ├── docx.py      # python-docx HTML→DOCX
    └── pdf.py       # weasyprint HTML→PDF
```

The Quip API returns thread content as HTML. All exporters accept that HTML
and write a file to a given Path. Add new formats by implementing
`export_<format>(html: str, output_path: Path) -> None` and wiring it into
`exporter.py` and `formats/__init__.py`.
