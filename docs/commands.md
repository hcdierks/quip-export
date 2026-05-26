# Command reference

## `quip-export sync`

Sync your entire Quip workspace to a local directory tree.

```
quip-export sync [OPTIONS]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output` | path | `.` | Directory to write files into |
| `--token` | text | — | Quip API token (overrides env / config) |
| `--dry-run` | flag | off | Preview only — no files written |
| `--verbose` | flag | off | Print INFO log lines to stdout |

### Examples

```bash
# Full sync to ./export
quip-export sync --output ./export

# Preview without writing anything
quip-export sync --output ./export --dry-run

# Verbose output (shows each exported file)
quip-export sync --output ./export --verbose

# Explicit token
quip-export sync --output ./export --token YOUR_TOKEN
```

### Output files written to `--output`

| File | When written | Description |
|------|-------------|-------------|
| `run.log` | Every run | Append-mode structured log (survives partial runs) |
| `run_state.md` | Every stage | Current pipeline stage; overwritten each step |
| `folders.md` | After discovery | All discovered folders with IDs and titles |
| `objects.md` | After classification | All classified threads |
| `exports.md` | After each export | Per-thread export results |
| `duplicates.md` | End of run | Threads that live in more than one folder |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | All documents exported successfully |
| `1` | One or more documents failed; the rest succeeded |
| `2` | Fatal error — nothing was exported (auth failure, API unreachable, permission denied on output dir) |

### `--dry-run` output

Dry-run exits 0 and prints a summary like:

```
Discovering folders...
  3 folder(s) found.
Classifying threads...
  12 thread(s) classified.

Dry-run summary (no files written):
  Would export to: /Users/you/quip-backup
  Folders discovered: 3
  Threads found: 12
    document: 8
    spreadsheet: 3
    slides: 1
  Estimated exports (incl. duplicates): 14
  Threads in multiple folders: 2
```

---

## `quip-export export` (single thread)

Export one or more specific Quip threads by ID.

```
quip-export export [OPTIONS] THREAD_IDS...
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output` | path | `.` | Directory to write files into |
| `--formats` | text (repeatable) | all | `md`, `docx`, or `pdf` |
| `--token` | text | — | Quip API token |

### Examples

```bash
# Export a thread to all formats
quip-export export AbCdEfGh

# Export to Markdown and PDF only
quip-export export AbCdEfGh --formats md --formats pdf

# Export multiple threads
quip-export export AbCdEfGh XyZwVuTs --output ./output
```

Thread IDs are visible in the Quip URL: `https://quip.com/AbCdEfGh`

---

## Log format

`run.log` entries follow this format:

```
[2026-05-25T18:34:01Z] [INFO] [sync] Run started — output: /path/to/export
[2026-05-25T18:34:02Z] [INFO] [sync] Discovered 3 folders
[2026-05-25T18:34:03Z] [INFO] [thread:AbCdEfGh] exported 'My Document'
[2026-05-25T18:34:04Z] [WARNING] [thread:XyZwVuTs] Export failed for 'Other Doc': ...
```

`WARNING` and `ERROR` lines are also printed to stderr. `INFO` lines go to stdout only
when `--verbose` is set. Token values are never written to the log.
