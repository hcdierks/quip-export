"""Root-level shared fixtures.

Only imports from the Python stdlib and already-existing quip_export modules so
that test *collection* never fails regardless of which features are built yet.
Feature-specific fixtures live in the per-subdirectory conftest.py files.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

FAKE_TOKEN = "test_token_1234567890abcdef"


@pytest.fixture()
def fake_token() -> str:
    return FAKE_TOKEN


# ---------------------------------------------------------------------------
# Sample HTML content (used across all export tests)
# ---------------------------------------------------------------------------

HTML_DOCUMENT = """
<html><body>
<h1>Quarterly Report</h1>
<h2>Executive Summary</h2>
<p>Revenue grew by <strong>12%</strong> this quarter.</p>
<p>See <em>Appendix A</em> for details.</p>
<h2>Key Metrics</h2>
<ul>
  <li>New customers: 142</li>
  <li>Churn rate: 3%</li>
</ul>
<ol>
  <li>Increase marketing spend</li>
  <li>Hire two engineers</li>
</ol>
<p>Contact <a href="mailto:cfo@example.com">CFO</a> for questions.</p>
<table>
  <tr><th>Region</th><th>Revenue</th></tr>
  <tr><td>EMEA</td><td>1.2M</td></tr>
  <tr><td>APAC</td><td>0.8M</td></tr>
</table>
</body></html>
"""

HTML_SPREADSHEET = """
<html><body>
<table>
  <tr><th>Name</th><th>Q1</th><th>Q2</th></tr>
  <tr><td>Alice</td><td>42</td><td>55</td></tr>
  <tr><td>Bob</td><td>38</td><td>47</td></tr>
</table>
</body></html>
"""

HTML_SLIDES = """
<html><body>
<div class="slide">
  <h1>Title Slide</h1>
  <p>Subtitle text here</p>
</div>
<div class="slide">
  <h1>Agenda</h1>
  <ul>
    <li>Introduction</li>
    <li>Results</li>
    <li>Next Steps</li>
  </ul>
</div>
</body></html>
"""

HTML_CHAT = """
<html><body>
<p><strong>Alice:</strong> Has anyone reviewed the doc?</p>
<p><strong>Bob:</strong> Yes, left some comments.</p>
</body></html>
"""

HTML_CODE = """
<html><body>
<pre><code>def hello():
    print("Hello, Quip!")
</code></pre>
</body></html>
"""

HTML_EMPTY = "<html><body></body></html>"

HTML_MALFORMED = "<html><body><h1>Unclosed heading<p>Text</body></html>"

HTML_WITH_IMAGE = """
<html><body>
<h1>Doc with image</h1>
<img src="blob/abc123/image.png" alt="chart" />
<p>Caption below image.</p>
</body></html>
"""


@pytest.fixture()
def html_document() -> str:
    return HTML_DOCUMENT


@pytest.fixture()
def html_spreadsheet() -> str:
    return HTML_SPREADSHEET


@pytest.fixture()
def html_slides() -> str:
    return HTML_SLIDES


@pytest.fixture()
def html_chat() -> str:
    return HTML_CHAT


@pytest.fixture()
def html_code() -> str:
    return HTML_CODE


@pytest.fixture()
def html_empty() -> str:
    return HTML_EMPTY


@pytest.fixture()
def html_malformed() -> str:
    return HTML_MALFORMED


@pytest.fixture()
def html_with_image() -> str:
    return HTML_WITH_IMAGE


# legacy alias kept for backwards compatibility with existing tests
@pytest.fixture()
def sample_html() -> str:
    return HTML_DOCUMENT


# ---------------------------------------------------------------------------
# Quip API response builders (plain dicts — no quip_export imports)
# ---------------------------------------------------------------------------

def make_thread_response(
    thread_id: str = "t1",
    title: str = "Test Doc",
    thread_class: str = "document",
    html: str = HTML_DOCUMENT,
) -> dict:
    return {
        "thread": {
            "id": thread_id,
            "title": title,
            "type": thread_class,
            "thread_class": "document",  # Real API: always "document" regardless of content type
        },
        "html": html,
    }


def make_folder_response(
    folder_id: str = "f1",
    title: str = "My Folder",
    child_folder_ids: list[str] | None = None,
    thread_ids: list[str] | None = None,
) -> dict:
    children = []
    for fid in (child_folder_ids or []):
        children.append({"folder_id": fid})
    for tid in (thread_ids or []):
        children.append({"thread_id": tid})
    return {
        "folder": {"id": folder_id, "title": title},
        "children": children,
    }


def make_user_response(
    user_id: str = "user1",
    private_folder_id: str = "f_private",
    shared_folder_ids: list[str] | None = None,
) -> dict:
    return {
        "current_user": {
            "id": user_id,
            "name": "Test User",
            "private_folder_id": private_folder_id,
            "shared_folder_ids": shared_folder_ids or [],
        }
    }


@pytest.fixture()
def sample_thread() -> dict:
    return make_thread_response()


@pytest.fixture()
def thread_response_factory():
    return make_thread_response


@pytest.fixture()
def folder_response_factory():
    return make_folder_response


@pytest.fixture()
def user_response_factory():
    return make_user_response
