"""Export Quip thread HTML to DOCX."""

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree


def _html_to_docx(html: str, doc: Document) -> None:
    """Minimal HTML-to-DOCX: renders block-level elements as paragraphs."""
    try:
        from lxml import html as lhtml  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError("lxml is required for DOCX export") from e

    root = lhtml.fromstring(html)
    _walk(root, doc)


def _walk(node: etree._Element, doc: Document) -> None:
    tag = node.tag if isinstance(node.tag, str) else ""

    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        doc.add_heading(node.text_content().strip(), level=level)
    elif tag == "p":
        doc.add_paragraph(node.text_content().strip())
    elif tag == "li":
        doc.add_paragraph(node.text_content().strip(), style="List Bullet")
    elif tag in ("ul", "ol", "div", "body", "html"):
        for child in node:
            _walk(child, doc)
    elif tag == "br":
        doc.add_paragraph()
    else:
        for child in node:
            _walk(child, doc)


def export_docx(html: str, output_path: Path) -> None:
    doc = Document()
    _html_to_docx(html, doc)
    doc.save(output_path)
