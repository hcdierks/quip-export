# Getting started

## What you need

### 1. A Quip API token

Log in to Quip, then go to:
**Settings → Developer → Personal API Access Token → Generate Token**

Direct URL: `https://quip.com/dev/token`

Copy the token — you will not be able to see it again.

### 2. Python 3.9 or newer

```bash
python3 --version   # must be 3.9+
```

### 3. On macOS: Pango (for PDF export)

PDF export uses WeasyPrint, which requires the Pango rendering library from Homebrew.
If you do not need PDFs you can skip this, but the tool will fail on PDF output without it.

```bash
brew install pango
```

---

## Installation

```bash
git clone https://github.com/hcdierks/quip-export.git
cd quip-export

python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -e .
```

Verify:
```bash
quip-export --help
```

---

## Providing your token

Choose one of these three methods (highest priority wins):

**Option A — environment variable (recommended for repeated use)**
```bash
export QUIP_TOKEN=your_token_here
quip-export sync --output ./export
```

**Option B — flag (good for one-off runs or scripts)**
```bash
quip-export sync --output ./export --token your_token_here
```

**Option C — config file (persists across shell sessions)**

Create `~/.config/quip-export/config.toml`:
```toml
token = "your_token_here"
```

---

## Your first sync

```bash
quip-export sync --output ./quip-backup
```

This will:
1. Authenticate with the Quip API
2. Walk your entire folder tree (Private + Shared folders)
3. Download and convert every document, spreadsheet, and slides deck
4. Write files into `./quip-backup/` mirroring your Quip folder structure

To preview what would be exported without writing any files:
```bash
quip-export sync --output ./quip-backup --dry-run
```

---

## What gets exported where

| Quip type | Output format |
|-----------|--------------|
| Document | `.docx` (falls back to `.md`) |
| Spreadsheet | `.xlsx` (falls back to `.md`) |
| Slides | `.pptx` (falls back to `.md`) |
| Chat / Code | `.md` |

A document that lives in multiple Quip folders is written to each corresponding
local folder. Duplicates are listed in `duplicates.md` in the output root.

---

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Everything exported successfully |
| 1 | At least one document failed; others succeeded |
| 2 | Fatal error (bad token, unreachable API, permission denied) |
