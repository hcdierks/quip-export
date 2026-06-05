# Release f7d7dd0 — 2026-06-05

| Field | Value |
|---|---|
| **Run** | 2026-06-05T15:56:39.400469+00:00 |
| **Commit** | [`f7d7dd0`](https://github.com/hcdierks/quip-export/commit/f7d7dd03e89a0a272b94b7298f557c090a5bc3e1) |
| **Tests** |  |
| **Security (SAST)** | Semgrep + pip-audit — see SAST workflow |
| **Security (DAST)** | Not applicable — CLI tool, no network service |

## Changes in this release

- audit: remove dead code, fix vacuous assertions, add PDF coverage, clean lint (d21dfc6)
- Fix #21: use type field for thread classification; thread_class is always 'document' (1d49928)
- Add .claude/ to .gitignore to prevent token leakage (c0d4fc2)
- Add README and MIT license for public release (4e26230)
- Fix #19: Quip API returns flat user object, not current_user-wrapped (8ad045c)
- Add docs: getting-started, commands, resilience, architecture (5fea459)
- Implement issues #12–16: logging, duplicates, sync CLI, retry, dry-run (c7c5d68)
- Implement issues #1–11: auth, discovery, format exports, fs, tracking (07a5905)
- Initial scaffold: quip-export Python CLI (4876fca)

## Security status

- SAST: Semgrep (p/python, p/owasp-top-ten, p/secrets) + pip-audit run on every push.
- DAST: Not applicable. This is a CLI tool with no network-accessible service endpoint.

## Known issues

- [#36](https://github.com/hcdierks/quip-export/issues/36) [security] DAST: not applicable — CLI/library, no network service
- [#35](https://github.com/hcdierks/quip-export/issues/35) [security] SAST: Semgrep + pip-audit in CI
