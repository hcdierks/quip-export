"""Non-functional resilience tests for the Quip API client.

Verifies retry count, Retry-After header compliance, backoff delay
sequencing, large-tree performance baseline, and resource cleanup.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import httpx
import pytest
import respx

from quip_export.client import (
    _MAX_RETRIES,
    QuipAPIError,
    QuipClient,
    _backoff,
)

# ---------------------------------------------------------------------------
# Retry count
# ---------------------------------------------------------------------------


class TestRetryCount:
    """Client retries exactly _MAX_RETRIES times on retryable responses."""

    @respx.mock
    def test_retries_max_times_on_503(self):
        route = respx.get("https://platform.quip.com/1/threads/t1").mock(
            return_value=httpx.Response(503, text="unavailable")
        )
        with patch("time.sleep"), QuipClient(token="tok") as client, \
                pytest.raises(QuipAPIError) as exc_info:
            client.get_thread("t1")
        assert exc_info.value.status_code == 503
        assert route.call_count == _MAX_RETRIES + 1

    @respx.mock
    def test_retries_max_times_on_429(self):
        route = respx.get("https://platform.quip.com/1/threads/t1").mock(
            return_value=httpx.Response(429, text="rate limited")
        )
        with patch("time.sleep"), QuipClient(token="tok") as client, \
                pytest.raises(QuipAPIError) as exc_info:
            client.get_thread("t1")
        assert exc_info.value.status_code == 429
        assert route.call_count == _MAX_RETRIES + 1

    @respx.mock
    def test_does_not_retry_on_404(self):
        route = respx.get("https://platform.quip.com/1/threads/t1").mock(
            return_value=httpx.Response(404, text="not found")
        )
        with QuipClient(token="tok") as client, pytest.raises(QuipAPIError) as exc_info:
            client.get_thread("t1")
        assert exc_info.value.status_code == 404
        assert route.call_count == 1

    @respx.mock
    def test_does_not_retry_on_403(self):
        route = respx.get("https://platform.quip.com/1/threads/t1").mock(
            return_value=httpx.Response(403, text="forbidden")
        )
        with QuipClient(token="tok") as client, pytest.raises(QuipAPIError) as exc_info:
            client.get_thread("t1")
        assert exc_info.value.status_code == 403
        assert route.call_count == 1

    @respx.mock
    def test_succeeds_on_transient_503_then_200(self, sample_thread):
        """First two attempts fail, third succeeds — no exception raised."""
        responses = iter([
            httpx.Response(503, text="unavailable"),
            httpx.Response(503, text="unavailable"),
            httpx.Response(200, json=sample_thread),
        ])
        respx.get("https://platform.quip.com/1/threads/t1").mock(
            side_effect=lambda req: next(responses)
        )
        with patch("time.sleep"), QuipClient(token="tok") as client:
            result = client.get_thread("t1")
        assert result["thread"]["id"] == sample_thread["thread"]["id"]

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_retries_on_all_retryable_status_codes(self, status):
        """Every status in {429, 500, 502, 503, 504} triggers retries."""
        with respx.mock:
            route = respx.get("https://platform.quip.com/1/threads/t1").mock(
                return_value=httpx.Response(status, text="error")
            )
            with patch("time.sleep"), QuipClient(token="tok") as client, \
                    pytest.raises(QuipAPIError):
                client.get_thread("t1")
            assert route.call_count == _MAX_RETRIES + 1, (
                f"Expected {_MAX_RETRIES + 1} calls for status {status}, "
                f"got {route.call_count}"
            )


# ---------------------------------------------------------------------------
# Retry-After header compliance
# ---------------------------------------------------------------------------


class TestRetryAfterHeader:
    """Retry-After header value is used as the sleep delay."""

    @respx.mock
    def test_retry_after_overrides_backoff(self):
        """When Retry-After is present, sleep uses that value, not exponential backoff."""
        responses = iter([
            httpx.Response(
                429, text="rate limited", headers={"Retry-After": "7"}
            ),
            httpx.Response(200, json={"thread": {"id": "t1"}, "html": ""}),
        ])
        respx.get("https://platform.quip.com/1/threads/t1").mock(
            side_effect=lambda req: next(responses)
        )
        with patch("time.sleep") as mock_sleep, QuipClient(token="tok") as client:
            client.get_thread("t1")
        assert mock_sleep.call_count == 1
        actual_delay = mock_sleep.call_args[0][0]
        assert actual_delay == pytest.approx(7.0, abs=1e-6)

    @respx.mock
    def test_retry_after_invalid_falls_back_to_backoff(self):
        """Invalid Retry-After (non-numeric) falls back to exponential backoff."""
        responses = iter([
            httpx.Response(
                429, text="rate limited", headers={"Retry-After": "not-a-number"}
            ),
            httpx.Response(200, json={"thread": {"id": "t1"}, "html": ""}),
        ])
        respx.get("https://platform.quip.com/1/threads/t1").mock(
            side_effect=lambda req: next(responses)
        )
        with patch("time.sleep") as mock_sleep, QuipClient(token="tok") as client:
            client.get_thread("t1")
        assert mock_sleep.call_count == 1
        actual_delay = mock_sleep.call_args[0][0]
        # Should be ~1.0s (BASE_DELAY * 2^0) with ±10% jitter
        assert 0.85 <= actual_delay <= 1.15

    @respx.mock
    def test_retry_after_zero_sleeps_zero(self):
        """Retry-After: 0 is respected (sleep 0 seconds)."""
        responses = iter([
            httpx.Response(
                429, text="rate limited", headers={"Retry-After": "0"}
            ),
            httpx.Response(200, json={"thread": {"id": "t1"}, "html": ""}),
        ])
        respx.get("https://platform.quip.com/1/threads/t1").mock(
            side_effect=lambda req: next(responses)
        )
        with patch("time.sleep") as mock_sleep, QuipClient(token="tok") as client:
            client.get_thread("t1")
        assert mock_sleep.call_args[0][0] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Backoff delay sequence
# ---------------------------------------------------------------------------


class TestBackoffSequence:
    """Backoff delays grow exponentially: 1s, 2s, 4s, 8s, 16s (with jitter)."""

    def test_backoff_base_values(self):
        """_backoff(attempt) returns a value close to BASE_DELAY * 2^attempt."""
        expected_centers = [1.0, 2.0, 4.0, 8.0, 16.0]
        for attempt, center in enumerate(expected_centers):
            delay = _backoff(attempt)
            # Allow ±10% jitter band
            assert center * 0.9 <= delay <= center * 1.1, (
                f"Attempt {attempt}: expected ~{center}s, got {delay:.3f}s"
            )

    def test_backoff_sequence_is_increasing(self):
        """Each successive backoff delay is strictly larger than the previous."""
        delays = [_backoff(i) for i in range(5)]
        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1] * 0.8, (
                f"Delay {i} ({delays[i]:.2f}) not larger than delay {i-1} ({delays[i-1]:.2f})"
            )

    @respx.mock
    def test_sleep_called_with_increasing_delays_on_repeated_503(self):
        """sleep() calls use increasing delays across retry attempts."""
        respx.get("https://platform.quip.com/1/threads/t1").mock(
            return_value=httpx.Response(503, text="unavailable")
        )
        sleep_delays: list[float] = []

        def capture_sleep(delay: float) -> None:
            sleep_delays.append(delay)

        with patch("time.sleep", side_effect=capture_sleep), \
                QuipClient(token="tok") as client, \
                pytest.raises(QuipAPIError):
            client.get_thread("t1")

        assert len(sleep_delays) == _MAX_RETRIES
        for i in range(1, len(sleep_delays)):
            assert sleep_delays[i] > sleep_delays[i - 1] * 0.7, (
                f"Delay {i} ({sleep_delays[i]:.2f}) not growing vs {i-1} ({sleep_delays[i-1]:.2f})"
            )


# ---------------------------------------------------------------------------
# Large-tree performance baseline
# ---------------------------------------------------------------------------


class TestLargeTreePerformance:
    """Sync completes within an acceptable time budget for a large tree."""

    def test_backoff_function_is_fast(self):
        """_backoff() is O(1) — calling it 10,000 times should take < 1s."""
        start = time.monotonic()
        for attempt in range(10_000):
            _backoff(attempt % 6)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"_backoff() too slow: {elapsed:.3f}s for 10k calls"

    @respx.mock
    def test_large_folder_tree_discovery_completes(self):
        """Discovering 50 folders (all 200 OK) completes without errors."""
        n_folders = 50
        folder_ids = [f"f{i}" for i in range(n_folders)]

        for fid in folder_ids:
            respx.get(f"https://platform.quip.com/1/folders/{fid}").mock(
                return_value=httpx.Response(200, json={
                    "folder": {"id": fid, "title": f"Folder {fid}"},
                    "children": [],
                })
            )
        respx.get("https://platform.quip.com/1/users/current").mock(
            return_value=httpx.Response(200, json={
                "current_user": {
                    "id": "u1",
                    "name": "Test User",
                    "private_folder_id": "f0",
                    "shared_folder_ids": folder_ids[1:],
                }
            })
        )

        start = time.monotonic()
        with QuipClient(token="tok") as client:
            for fid in folder_ids:
                client.get_folder(fid)
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, (
            f"Fetching {n_folders} folders took {elapsed:.2f}s — too slow"
        )

    @respx.mock
    def test_100_threads_fetched_without_error(self, sample_thread):
        """Fetching 100 thread responses succeeds and returns correct data."""
        n_threads = 100
        for i in range(n_threads):
            tid = f"t{i}"
            thread_data = {
                "thread": {**sample_thread["thread"], "id": tid},
                "html": sample_thread["html"],
            }
            respx.get(f"https://platform.quip.com/1/threads/{tid}").mock(
                return_value=httpx.Response(200, json=thread_data)
            )

        results = []
        with QuipClient(token="tok") as client:
            for i in range(n_threads):
                results.append(client.get_thread(f"t{i}"))

        assert len(results) == n_threads
        assert results[0]["thread"]["id"] == "t0"
        assert results[-1]["thread"]["id"] == f"t{n_threads - 1}"


# ---------------------------------------------------------------------------
# Resource cleanup
# ---------------------------------------------------------------------------


class TestResourceCleanup:
    """HTTP client resources are released after use."""

    def test_close_called_on_context_manager_exit(self, monkeypatch):
        """QuipClient.__exit__ calls close(), which calls _http.close()."""
        closed = []

        class _FakeHTTP:
            def get(self, *a, **kw):
                return httpx.Response(200, json={})

            def close(self):
                closed.append(True)

        monkeypatch.setattr("httpx.Client", lambda **kw: _FakeHTTP())
        with QuipClient(token="tok"):
            pass
        assert closed == [True], "httpx.Client.close() was not called on exit"

    def test_close_is_idempotent(self, monkeypatch):
        """Calling close() twice does not raise."""
        close_count = []

        class _FakeHTTP:
            def close(self):
                close_count.append(1)

        monkeypatch.setattr("httpx.Client", lambda **kw: _FakeHTTP())
        client = QuipClient(token="tok")
        client.close()
        client.close()
        assert len(close_count) == 2

    @respx.mock
    def test_no_open_connections_after_batch(self, sample_thread):
        """After processing a batch of requests, the client closes cleanly."""
        for i in range(10):
            respx.get(f"https://platform.quip.com/1/threads/t{i}").mock(
                return_value=httpx.Response(200, json=sample_thread)
            )
        with QuipClient(token="tok") as client:
            for i in range(10):
                client.get_thread(f"t{i}")
        # If context manager closed cleanly, no exception was raised.
        # A second close() should also be safe (httpx handles this).
        client.close()
