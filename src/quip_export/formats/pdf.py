"""Export Quip thread HTML to PDF via WeasyPrint."""

from pathlib import Path

import weasyprint

_CSS = weasyprint.CSS(string="""
    body { font-family: sans-serif; font-size: 12pt; margin: 2cm; }
    h1, h2, h3 { color: #1a1a1a; }
    pre, code { font-family: monospace; background: #f5f5f5; padding: 2px 4px; }
""")


def export_pdf(html: str, output_path: Path) -> None:
    weasyprint.HTML(string=html).write_pdf(output_path, stylesheets=[_CSS])
