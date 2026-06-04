# Requirements

This document maps each functional requirement to its GitHub issue and
implementation status.

**Status key:** ✅ Implemented and closed · 🅿️ Parking lot (deliberate deferral)

---

## Authentication

### REQ-01 — Token configuration and validation
Users can supply a Quip API token via CLI flag, environment variable, or config file. Resolution priority: `--token` flag > `QUIP_TOKEN` env var > `~/.config/quip-export/config.toml`. A missing or empty token raises a clear auth error before any API calls are made.

**Acceptance criteria:**
- `--token` flag takes precedence over all other sources
- `QUIP_TOKEN` env var is used when no flag is supplied
- Config file at `~/.config/quip-export/config.toml` with `token = "..."` is used as last resort
- Missing token produces a human-readable error and exits with code 2

**Issue:** [#1](https://github.com/hcdierks/quip-export/issues/1) · **Status:** ✅

---

## Discovery

### REQ-02 — Fetch Quip folder hierarchy recursively
The sync command walks the user's entire Quip workspace (private root + shared roots) and builds an in-memory folder tree. Cycles are detected and skipped; 403/404 folders are skipped with a log warning.

**Acceptance criteria:**
- Private root and all shared roots are enumerated via `GET /users/current`
- BFS walk descends into all child folders
- Cycles in the folder graph do not cause infinite loops
- Inaccessible folders (403/404) are skipped without aborting the sync

**Issue:** [#2](https://github.com/hcdierks/quip-export/issues/2) · **Status:** ✅

### REQ-03 — Mirror Quip folder tree as local directories
The local output directory mirrors the Quip folder hierarchy exactly. Each Quip folder becomes a subdirectory; naming is sanitised (special characters replaced with `_`) to be filesystem-safe.

**Acceptance criteria:**
- Output directory structure matches the Quip folder hierarchy depth for depth
- Folder names are sanitised: characters outside `[A-Za-z0-9 \-_.]` are replaced with `_`
- Empty folders are created

**Issue:** [#3](https://github.com/hcdierks/quip-export/issues/3) · **Status:** ✅

### REQ-04 — List and classify all objects within folders
Each thread in the workspace is classified by its Quip type (document, spreadsheet, slides, chat, code) so the exporter can choose the right output format.

**Acceptance criteria:**
- Every thread reachable from the folder tree is enumerated
- Threads that appear in multiple folders are tracked with all folder memberships
- Classification maps `thread_class` to the correct `FormatSpec`

**Issue:** [#4](https://github.com/hcdierks/quip-export/issues/4) · **Status:** ✅

---

## Export formats

### REQ-05 — Format dispatch table
A central `FORMAT_MAP` maps Quip thread types to output format specs. Unrecognised types fall back to Markdown. Lookup is case-insensitive.

**Acceptance criteria:**
- `document` → `.docx`; `spreadsheet` → `.xlsx`; `slides` → `.pptx`; `chat`/`code`/`unknown` → `.md`
- Unrecognised types return `.md` without raising
- Lookup is case-insensitive

**Issue:** [#5](https://github.com/hcdierks/quip-export/issues/5) · **Status:** ✅

### REQ-06 — Export Quip documents to DOCX with rich formatting
Documents are exported to `.docx` preserving headings (H1–H6), bold, italic, hyperlinks, unordered/ordered lists, and tables.

**Acceptance criteria:**
- H1/H2 headings preserved as Word heading styles
- Bold and italic inline formatting preserved
- Hyperlink text preserved
- Ordered and unordered list items present
- Tables exported with correct row/column structure
- Images replaced with `[image]` placeholder text (see REQ-PL-01)

**Issue:** [#6](https://github.com/hcdierks/quip-export/issues/6) · **Status:** ✅

### REQ-07 — Export Quip spreadsheets to XLSX
Spreadsheet HTML is exported to `.xlsx`. Numeric cells are coerced to numbers; bold header rows are preserved; formula-like strings (`=...`) are prefixed with `'` to prevent Excel evaluation.

**Acceptance criteria:**
- All table rows and columns present
- Numeric strings coerced to float where possible
- Bold header row formatting applied
- Strings starting with `=` stored as `'=...` to prevent formula evaluation

**Issue:** [#7](https://github.com/hcdierks/quip-export/issues/7) · **Status:** ✅

### REQ-08 — Export Quip slides/presentations to PPTX
Each `<div class="slide">` becomes one PPTX slide with H1 as title and body content as bullet points. When no slide divs are present and the body has content, a single slide is created from the full body. Empty body → zero slides.

**Acceptance criteria:**
- Each slide div produces one PPTX slide
- H1 within the div becomes the slide title
- Body content (p, li) becomes bullet text
- No slide divs + body content → one slide from full body
- Empty body → zero slides output

**Issue:** [#8](https://github.com/hcdierks/quip-export/issues/8) · **Status:** ✅

### REQ-09 — Markdown as primary format and automatic fallback
All thread types can be exported to Markdown. For documents, spreadsheets, and slides, if the primary format exporter raises an exception, the sync continues with a Markdown fallback rather than failing the entire export.

**Acceptance criteria:**
- `export_markdown()` handles any well-formed or malformed HTML without raising
- `export_with_fallback()` falls back to `.md` when primary exporter raises
- Chat, code, and unknown types always go directly to Markdown (no primary attempt)
- Fallback produces a non-empty `.md` file

**Issue:** [#9](https://github.com/hcdierks/quip-export/issues/9) · **Status:** ✅

### REQ-10 — Export Quip documents to PDF
Documents can be exported to `.pdf` via WeasyPrint with standard page layout, sans-serif font, and monospace code formatting.

**Acceptance criteria:**
- `export_pdf()` calls WeasyPrint with the supplied HTML and CSS stylesheet
- CSS applies: `font-family: sans-serif`, `font-size: 12pt`, `margin: 2cm`, monospace code blocks
- WeasyPrint errors propagate to the caller (not silently swallowed)

**Status:** ✅ (part of initial implementation; dedicated test coverage added in issue #23)

---

## Sync pipeline

### REQ-11 — Real-time progress state files written during run
During a sync, progress is recorded to `run_state.md`, `folders.md`, `objects.md`, and `exports.md` in the output directory so that an interrupted run can be inspected.

**Acceptance criteria:**
- `run_state.md` updated at each pipeline stage (`classifying`, `exporting`, `done`)
- `folders.md` written after discovery completes
- `objects.md` appended per thread after classification
- `exports.md` appended per thread after export

**Issue:** [#11](https://github.com/hcdierks/quip-export/issues/11) · **Status:** ✅

### REQ-12 — Logging: Structured error and warning log file
All sync events are written to `run.log` with `[TIMESTAMP] [LEVEL] [CONTEXT] MESSAGE` format. The run token is scrubbed from all log lines. INFO events are written to `run.log` only; WARNING/ERROR always go to stderr as well.

**Acceptance criteria:**
- `run.log` created in output directory; appended across runs
- Token value never appears in log (scrubbed to `***`)
- WARNING and ERROR lines emitted to stderr as well as `run.log`
- INFO lines to `run.log` only (unless `--verbose`)

**Issue:** [#12](https://github.com/hcdierks/quip-export/issues/12) · **Status:** ✅

### REQ-13 — Duplicates report: export to all parent folders, track duplicates
Threads that appear in multiple Quip folders are exported to each folder on disk. After the sync, a `duplicates.md` report lists all threads that were written to more than one location.

**Acceptance criteria:**
- A thread with N folder memberships is written to N local directories
- Each copy is independent (separate file per directory)
- `duplicates.md` written after all exports; lists thread ID, title, and all paths

**Issue:** [#10](https://github.com/hcdierks/quip-export/issues/10) + [#13](https://github.com/hcdierks/quip-export/issues/13) · **Status:** ✅

### REQ-14 — CLI: quip-export sync command — full pipeline orchestration
The `sync` command runs the full discovery → classification → export pipeline. Exit codes: 0 = full success, 1 = partial failure (≥1 thread failed), 2 = fatal error (discovery or classification failed).

**Acceptance criteria:**
- `sync` command accepts `--output`, `--token`, `--verbose`, `--dry-run`
- Exit code 0 when all threads exported successfully
- Exit code 1 when at least one thread export fails (others continue)
- Exit code 2 on discovery or classification failure

**Issue:** [#14](https://github.com/hcdierks/quip-export/issues/14) · **Status:** ✅

### REQ-15 — Resilience: Quip API rate limiting and retry with exponential backoff
The API client retries automatically on transient errors (HTTP 429, 500, 502, 503, 504, and network timeouts) with exponential backoff ± 10% jitter and `Retry-After` header support. Non-transient 4xx errors raise immediately.

**Acceptance criteria:**
- HTTP 429/5xx retried up to 5 times with backoff: 1 s, 2 s, 4 s, 8 s, 16 s ± 10% jitter
- `Retry-After` header respected when present for 429 responses
- Network timeouts retried up to 5 times
- Non-retryable 4xx (except 429) raise `QuipAPIError` immediately

**Issue:** [#15](https://github.com/hcdierks/quip-export/issues/15) · **Status:** ✅

### REQ-16 — CLI: --dry-run mode — preview sync without writing files
`--dry-run` runs discovery and classification but writes nothing to disk. Prints a summary: folders found, threads by type, estimated export count, threads in multiple folders.

**Acceptance criteria:**
- No files or directories created under `output`
- Summary printed to stdout listing folder count, thread count by type, estimated exports, and duplicate count
- Exit code 0

**Issue:** [#16](https://github.com/hcdierks/quip-export/issues/16) · **Status:** ✅

---

## Bug fixes

### REQ-17 — Fix: `GET /users/current` returns flat object, not wrapped
The Quip API returns the current user as a flat JSON object, not wrapped in a `current_user` key as initially assumed. Discovery was failing to read `private_folder_id` and `shared_folder_ids`.

**Issue:** [#19](https://github.com/hcdierks/quip-export/issues/19) · **Status:** ✅

### REQ-18 — Fix: spreadsheets and slides misclassified as documents
The `thread_class` field was being read from the wrong key in the Quip API response. Spreadsheets and slides were always classified as `document`, causing incorrect format dispatch.

**Issue:** [#21](https://github.com/hcdierks/quip-export/issues/21) · **Status:** ✅

---

## Parking lot (deliberate deferrals)

### REQ-PL-01 — Inline image export (blob downloads)
Images in Quip documents are referenced as `<img src="blob/{thread_id}/{name}">`. Downloading and embedding these inline requires `GET /blob/...` support in the client and format-specific embedding in DOCX (InlineImage), PPTX (picture shape), and PDF/Markdown (local path).

Currently: images replaced with `[image]` placeholder text in DOCX/PPTX; src URL preserved in Markdown.

**Issue:** [#25](https://github.com/hcdierks/quip-export/issues/25) · **Status:** 🅿️

### REQ-PL-02 — Token pre-flight check command (`quip-export check`)
A `check` subcommand that calls `GET /users/current` to verify the configured token is valid, printing the authenticated user name on success and a clear auth error on failure. Useful for onboarding and debugging.

**Issue:** [#26](https://github.com/hcdierks/quip-export/issues/26) · **Status:** 🅿️
