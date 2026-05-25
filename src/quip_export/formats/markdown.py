"""Export Quip thread HTML to Markdown."""

from pathlib import Path

import markdownify


def export_markdown(html: str, output_path: Path) -> None:
    md = markdownify.markdownify(html, heading_style="ATX", strip=["script", "style"])
    output_path.write_text(md, encoding="utf-8")
