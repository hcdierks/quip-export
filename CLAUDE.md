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

### Export single threads (legacy command)

```bash
quip-export THREAD_ID                          # all formats to current dir
quip-export THREAD_ID -o ./output -f md -f pdf # specific formats and output dir
python -m quip_export THREAD_ID                # run without installing
```

### Sync entire workspace

```bash
quip-export sync --output ./export             # full workspace sync
quip-export sync --output ./export --verbose   # show INFO events on stdout
quip-export sync --output ./export --dry-run   # preview without writing files
quip-export sync --output ./export --token TOK # override QUIP_TOKEN
```

**Exit codes:** 0 = full success · 1 = partial failure (≥1 export failed) · 2 = fatal error

**`--dry-run`**: authenticates and runs full discovery + classification but writes
nothing to disk. Prints a summary of folders, thread counts by type, estimated
exports, and duplicate count.

**`--verbose`**: also prints `INFO` log entries to stdout (WARNING/ERROR always
go to stderr regardless).

## Output files

After `sync`, the output directory contains:

| File | Description |
|------|-------------|
| `run.log` | Append-mode structured log: `[TIMESTAMP] [LEVEL] [CONTEXT] MESSAGE` |
| `run_state.md` | Current pipeline stage (overwritten each stage) |
| `folders.md` | All discovered folders with IDs and titles |
| `objects.md` | All classified threads (appended as discovered) |
| `exports.md` | Export results per thread (appended as written) |
| `duplicates.md` | Threads exported to multiple folders (overwritten per run) |

## Resilience

The Quip API client retries automatically on transient errors:

- **Retryable:** HTTP 429, 500, 502, 503, 504, and network timeouts
- **Not retried:** HTTP 4xx (except 429) — these raise `QuipAPIError` immediately
- **Strategy:** exponential backoff (1 s, 2 s, 4 s, 8 s, 16 s) ± 10 % jitter, up to 5 retries
- **Retry-After header:** respected for 429 responses when present

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

- Write all tests before production code (TDD). Test layer order: unit → functional → integration → nfr.
- Always update tests and docs alongside every code change.
- Never commit `.env` or any file containing a `QUIP_TOKEN`.
- Keep `CLAUDE.md` up to date when adding new commands or changing the API.

## Architecture

```
src/quip_export/
├── cli.py           # typer CLI — export (single-thread) + sync (full workspace)
├── client.py        # httpx Quip API client with retry + backoff
├── auth.py          # token resolution: flag > QUIP_TOKEN env > config file
├── discovery.py     # folder tree walk + thread classification
├── exporter.py      # export_with_fallback + export_classified_thread
├── fs.py            # sanitise_name + create_directory_structure
├── models.py        # FolderNode / FolderTree / ClassifiedThread / DuplicateRecord
├── run_logger.py    # RunLogger: structured run.log with immediate flush
├── tracking.py      # StateTracker + write_duplicates_report
└── formats/
    ├── __init__.py  # FORMAT_MAP + get_format()
    ├── markdown.py  # HTML → MD (markdownify)
    ├── docx.py      # HTML → DOCX (python-docx, inline formatting + tables)
    ├── xlsx.py      # HTML → XLSX (openpyxl, numeric coercion, bold headers)
    ├── pptx.py      # HTML → PPTX (python-pptx, slide-div aware)
    └── pdf.py       # HTML → PDF (weasyprint)
```

The Quip API returns thread content as HTML. All exporters accept that HTML
and write a file to a given Path. Add new formats by implementing
`export_<format>(html: str, output_path: Path) -> None` and wiring it into
`exporter.py` and `formats/__init__.py`.

### Token resolution order

`--token` flag → `QUIP_TOKEN` environment variable → `~/.config/quip-export/config.toml` (`token = "..."`)
