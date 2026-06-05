# Security

## Threat model

quip-export is a CLI tool that exports Quip documents to local files.
It authenticates to the Quip API and writes output files locally.
It has no network-accessible service endpoint.

**Attack surface:**
- Quip API: reads documents using a user-supplied access token
- Local filesystem: writes exported files to a user-specified directory
- No inbound network exposure

---

## SAST (Static Application Security Testing)

**Tooling:** Semgrep + pip-audit

**Cadence:** every push to `main`, every pull request, weekly scheduled scan.

**Scope:**
- Python source (`src/`) — Semgrep rulesets: `p/python`, `p/owasp-top-ten`, `p/secrets`
- Dependencies — `pip-audit --strict`

**Current status:** see latest SAST workflow run for results.

---

## DAST (Dynamic Application Security Testing)

**Not applicable.**

This project is a CLI tool with no network-accessible service endpoint.
OWASP ZAP and equivalent tools require an HTTP target to scan.

**Due diligence:** DAST confirmed inapplicable. See GitHub issue #36.

---

## Known controls

| Control | Implementation |
|---|---|
| No secrets in code | Quip token passed via env var or CLI flag, never hardcoded |
| Dependency scanning | pip-audit on every CI run |
| Static analysis | Semgrep on every push |
| Local-only output | No network service, no inbound exposure |

---

## Reporting a vulnerability

Open a GitHub issue with the `security` label or email henner@hdierks.org.
