# quip-export

**Export your Quip workspace before it's gone.**

Salesforce is retiring Quip. This tool exports your entire workspace — documents, spreadsheets, and slides — to standard open formats on your local machine, preserving your folder structure.

---

## Background

Quip was acquired by Salesforce in 2016 and has been a widely used collaborative document platform. Salesforce has announced it is retiring Quip, leaving users with a limited window to export their data before it becomes inaccessible.

`quip-export` was built specifically for this migration. It walks your entire Quip folder tree, downloads every document, and converts it to an open format you can open without Quip:

| Quip type | Exported as |
|-----------|-------------|
| Document | `.docx` (Microsoft Word) |
| Spreadsheet | `.xlsx` (Microsoft Excel) |
| Slides | `.pptx` (Microsoft PowerPoint) |
| Chat / Code | `.md` (Markdown) |

If a primary format conversion fails for any document, the tool automatically falls back to Markdown so you never lose content.

---

## Prerequisites

### Python 3.9 or newer

```bash
python3 --version
```

### A Quip API token

1. Log in to Quip
2. Go to **Settings → Developer → Personal API Access Token**
   - Direct URL: `https://quip.com/dev/token`
3. Click **Generate Token** and copy it — you will not see it again

### macOS only: Pango (for PDF export)

PDF export uses WeasyPrint, which requires the Pango text rendering library. If you do not need PDF output, skip this.

```bash
brew install pango
```

---

## Installation

### From source (recommended while in active development)

```bash
git clone https://github.com/hcdierks/quip-export.git
cd quip-export

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

pip install -e .
```

Verify:

```bash
quip-export --help
```

---

## Quick start

### 1. Set your token

```bash
export QUIP_TOKEN=your_token_here
```

Or pass it directly with `--token YOUR_TOKEN` on any command.

### 2. Preview what will be exported (no files written)

```bash
quip-export sync --output ./quip-backup --dry-run
```

This authenticates, walks your entire folder tree, and prints a summary:

```
Discovering folders...
  125 folder(s) found.
Classifying threads...
  343 thread(s) classified.

Dry-run summary (no files written):
  Would export to: /Users/you/quip-backup
  Folders discovered: 125
  Threads found: 343
    document: 343
  Estimated exports (incl. duplicates): 343
  Threads in multiple folders: 0
```

### 3. Run the full export

```bash
quip-export sync --output ./quip-backup
```

Your Quip folder structure is mirrored under `./quip-backup/`. A progress log is written to `quip-backup/run.log` as the export runs.

---

## Commands

### `quip-export sync` — export your entire workspace

```
quip-export sync [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--output PATH` | Directory to write files into (default: current directory) |
| `--token TEXT` | Quip API token — overrides `QUIP_TOKEN` env var |
| `--dry-run` | Preview only: no files are written |
| `--verbose` | Print INFO log lines to stdout as the export runs |

**Exit codes:** `0` = success · `1` = partial failure (some docs failed, others succeeded) · `2` = fatal error

### `quip-export export` — export specific threads by ID

```
quip-export export [OPTIONS] THREAD_IDS...
```

| Option | Description |
|--------|-------------|
| `--output PATH` | Directory to write files into |
| `--formats TEXT` | `md`, `docx`, or `pdf` — repeatable; defaults to all |
| `--token TEXT` | Quip API token |

Thread IDs appear in Quip URLs: `https://quip.com/AbCdEfGhIjKl`

---

## Output files

After a `sync`, the output directory contains your exported documents in a folder tree matching your Quip workspace, plus these state files in the root:

| File | Description |
|------|-------------|
| `run.log` | Structured log of every action and error |
| `run_state.md` | Current pipeline stage (useful if the run is interrupted) |
| `folders.md` | All discovered folders with their Quip IDs |
| `objects.md` | All classified threads |
| `exports.md` | Per-thread export results |
| `duplicates.md` | Documents that appear in more than one folder |

---

## Token storage options

The token is resolved in this priority order:

1. `--token` flag on the command line
2. `QUIP_TOKEN` environment variable
3. `~/.config/quip-export/config.toml`:
   ```toml
   token = "your_token_here"
   ```

The token is never written to `run.log` — it is scrubbed before any log line is flushed.

---

## Resilience

Large workspaces often trigger Quip API rate limits. `quip-export` handles this automatically:

- **Retried:** HTTP 429 (rate limited), 500/502/503/504 (server errors), network timeouts
- **Not retried:** HTTP 4xx errors other than 429 — raised immediately
- **Backoff:** exponential (1 s → 2 s → 4 s → 8 s → 16 s) with ±10% jitter, up to 5 retries
- **Retry-After header:** respected when the API sends one (Quip sometimes sends 27–38 s)
- **Partial failure:** if one document fails, the rest of the workspace still exports

If the run is interrupted (Ctrl+C or crash), re-running to the same `--output` directory resumes safely — already-exported files are overwritten in place and `run.log` is appended.

---

## Development

Contributions are welcome. The project uses strict TDD — all tests must pass before any change is merged.

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (sets DYLD_LIBRARY_PATH for WeasyPrint on macOS)
make test

# Lint
make lint

# Type check
make typecheck
```

### Adding a new export format

1. Create `src/quip_export/formats/<name>.py` with `export_<name>(html: str, path: Path) -> None`
2. Add it to `FORMAT_MAP` in `formats/__init__.py`
3. Add a branch in `exporter.py::export_with_fallback()`
4. Write tests in `tests/unit/test_export_<name>.py`

See [docs/architecture.md](docs/architecture.md) for the full module map and pipeline diagram.

---

## Documentation

- [Getting started](docs/getting-started.md) — token setup, install, first run
- [Command reference](docs/commands.md) — all flags, output files, log format
- [Resilience](docs/resilience.md) — retry schedule, partial failures, format fallback
- [Architecture](docs/architecture.md) — module map, sync pipeline, how to extend

---

## License

MIT — see [LICENSE](LICENSE).
