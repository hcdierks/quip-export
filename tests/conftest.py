"""Shared fixtures for quip-export tests."""

import pytest

SAMPLE_HTML = """
<html><body>
<h1>Test Document</h1>
<p>A paragraph of text.</p>
<ul><li>Item one</li><li>Item two</li></ul>
</body></html>
"""

SAMPLE_THREAD_RESPONSE = {
    "thread": {"id": "abc123", "title": "Test Document"},
    "html": SAMPLE_HTML,
}


@pytest.fixture()
def sample_html() -> str:
    return SAMPLE_HTML


@pytest.fixture()
def sample_thread() -> dict:
    return SAMPLE_THREAD_RESPONSE
