# Resilience and error handling

## API retries

The Quip client retries automatically on transient failures.

| Trigger | Behaviour |
|---------|-----------|
| HTTP 429 (rate limited) | Retry up to 5 times; uses `Retry-After` header delay when present |
| HTTP 500, 502, 503, 504 | Retry up to 5 times with exponential backoff |
| Network timeout | Retry up to 5 times with exponential backoff |
| HTTP 4xx (except 429) | Raised immediately — not retried |

### Backoff schedule

Without a `Retry-After` header, delays follow exponential backoff with ±10% jitter:

| Attempt | Base delay | Actual range |
|---------|-----------|-------------|
| 1 | 1 s | 0.9 – 1.1 s |
| 2 | 2 s | 1.8 – 2.2 s |
| 3 | 4 s | 3.6 – 4.4 s |
| 4 | 8 s | 7.2 – 8.8 s |
| 5 | 16 s | 14.4 – 17.6 s |

After five failures the client raises `QuipAPIError` and the affected thread is
counted as failed in the sync summary.

---

## Partial failures

`sync` is fault-tolerant at the thread level. If one document fails to export
(network error, corrupted HTML, disk full), the rest of the workspace still
exports. The run exits with code `1` and the failure is logged to `run.log`.

---

## Format fallback

If the primary exporter for a thread type fails, the thread is re-exported as
Markdown:

```
document  → .docx  (fallback: .md)
spreadsheet → .xlsx (fallback: .md)
slides    → .pptx  (fallback: .md)
chat/code → .md    (no fallback needed)
```

The fallback is logged at WARNING level.

---

## Interrupted runs

Pressing Ctrl+C writes a final log entry and exits with code 2. The output
directory and any files already written are left in place. Re-running
`quip-export sync` to the same `--output` directory will overwrite state files
but append to `run.log`, so you retain the history of both runs.

---

## Disk and permission errors

- If the output directory cannot be created (e.g. no write permission), the run
  exits immediately with code 2 and nothing is written.
- If an individual file cannot be written (e.g. disk full mid-run), that thread
  is counted as failed and the run continues.
- State files (`run_state.md`, `folders.md`, etc.) are written atomically via a
  `.tmp` + rename pattern to prevent partial writes from corrupting them.
