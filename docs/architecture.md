# Architecture

## Module map

```
src/quip_export/
├── cli.py           CLI entry point (Typer)
│                      commands: export, sync
│                      flags: --output, --token, --dry-run, --verbose
│
├── auth.py          Token resolution
│                      priority: --token flag > QUIP_TOKEN env > ~/.config/quip-export/config.toml
│
├── client.py        Quip REST API client (httpx)
│                      retry + exponential backoff on 429 / 5xx / timeouts
│
├── discovery.py     Folder tree walk + thread classification
│                      discover_folders()   → FolderTree
│                      list_and_classify()  → list[ClassifiedThread]
│
├── exporter.py      Thread export orchestration
│                      export_thread()              single-thread export (legacy)
│                      export_with_fallback()        format dispatch with .md fallback
│                      export_classified_thread()    multi-folder-aware export
│
├── fs.py            Local filesystem helpers
│                      sanitise_name()             safe filename from Quip title
│                      create_directory_structure() mirror folder tree on disk
│
├── models.py        Data classes
│                      FolderNode, FolderTree
│                      ClassifiedThread, DuplicateRecord
│
├── run_logger.py    Structured run log
│                      RunLogger → run.log
│                      token scrubbing, immediate flush
│
├── tracking.py      State files
│                      StateTracker → run_state.md, folders.md, objects.md, exports.md
│                      write_duplicates_report() → duplicates.md
│
└── formats/
    ├── __init__.py  Format dispatch table (FORMAT_MAP, get_format())
    ├── markdown.py  HTML → Markdown (markdownify)
    ├── docx.py      HTML → DOCX (python-docx)
    ├── xlsx.py      HTML → XLSX (openpyxl)
    ├── pptx.py      HTML → PPTX (python-pptx)
    └── pdf.py       HTML → PDF (weasyprint)
```

---

## Sync pipeline

```
resolve_token()
      │
      ▼
mkdir(output_dir)  ──── PermissionError → exit 2
RunLogger + StateTracker
      │
      ▼
discover_folders(client)   ──── Exception → exit 2
      │  BFS over Private + Shared roots
      │  cycle detection, 403/404 skipped
      ▼
list_and_classify(client, tree)   ──── Exception → exit 2
      │  fetches thread metadata for each folder
      │  merges multi-folder threads
      ▼
create_directory_structure(tree, output_dir)
      │  mirrors Quip folder hierarchy locally
      ▼
for each thread:
    client.get_thread()  (retried on 429 / 5xx)
    export_classified_thread()
          │  export_with_fallback() → .docx/.xlsx/.pptx or .md
          │  written to each folder the thread belongs to
      failed? → count += 1, log warning, continue
      │
      ▼
write_duplicates_report()
      │
      ▼
exit 0  (or exit 1 if any failures)
```

---

## Adding a new export format

1. Create `src/quip_export/formats/<name>.py` with:
   ```python
   def export_<name>(html: str, output_path: Path) -> None: ...
   ```

2. Import it in `formats/__init__.py` and add an entry to `FORMAT_MAP`:
   ```python
   "slides": FormatSpec(".pptx", export_pptx),   # existing example
   "<class>": FormatSpec(".<ext>", export_<name>),
   ```

3. Add the import to `exporter.py` and add a branch in `export_with_fallback()`.

4. Write tests in `tests/unit/test_export_<name>.py`.

---

## Token resolution order

```
--token flag
    │  (if provided)
    ▼
QUIP_TOKEN environment variable
    │  (if set and non-empty)
    ▼
~/.config/quip-export/config.toml  →  token = "..."
    │  (if file exists and token key is set)
    ▼
QuipAuthError  →  exit 2
```

The token value is never written to `run.log` — it is scrubbed to `***` before
any log line is flushed.
