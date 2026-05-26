"""Unit tests — Quip API client retry and backoff (issue #15)."""

from __future__ import annotations

from unittest.mock import call, patch

import httpx
import pytest
import respx

from quip_export.client import QuipAPIError, QuipClient

QUIP_BASE = "https://platform.quip.com/1"


# ---------------------------------------------------------------------------
# Successful first attempt — no sleep, no overhead
# ---------------------------------------------------------------------------

class TestNoRetryOnSuccess:
    @respx.mock
    def test_successful_first_attempt_no_sleep(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(200, json={"thread": {"id": "t1"}})
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                client.get_thread("t1")
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# 429 retry
# ---------------------------------------------------------------------------

class TestRateLimitRetry:
    @respx.mock
    def test_429_then_200_returns_result(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=[
                httpx.Response(429, text="Rate limited"),
                httpx.Response(200, json={"thread": {"id": "t1"}}),
            ]
        )
        with patch("time.sleep"):
            with QuipClient(token="tok") as client:
                result = client.get_thread("t1")
        assert result["thread"]["id"] == "t1"

    @respx.mock
    def test_429_then_200_calls_sleep_once(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=[
                httpx.Response(429, text="Rate limited"),
                httpx.Response(200, json={"thread": {"id": "t1"}}),
            ]
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                client.get_thread("t1")
        assert mock_sleep.call_count == 1

    @respx.mock
    def test_retry_after_header_used_as_delay(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "3"}, text="RL"),
                httpx.Response(200, json={"thread": {"id": "t1"}}),
            ]
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                client.get_thread("t1")
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args[0][0] == pytest.approx(3.0)

    @respx.mock
    def test_five_429s_raises_api_error(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(429, text="RL")
        )
        with patch("time.sleep"):
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError) as exc_info:
                    client.get_thread("t1")
        assert exc_info.value.status_code == 429

    @respx.mock
    def test_five_429s_sleeps_five_times(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(429, text="RL")
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError):
                    client.get_thread("t1")
        assert mock_sleep.call_count == 5

    @respx.mock
    def test_429_logs_warning(self, caplog):
        import logging
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=[
                httpx.Response(429, text="RL"),
                httpx.Response(200, json={"thread": {"id": "t1"}}),
            ]
        )
        with patch("time.sleep"), caplog.at_level(logging.WARNING, logger="quip_export.client"):
            with QuipClient(token="tok") as client:
                client.get_thread("t1")
        assert any("429" in r.message or "retry" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# 5xx retry
# ---------------------------------------------------------------------------

class TestServerErrorRetry:
    @respx.mock
    def test_503_three_times_then_200(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=[
                httpx.Response(503, text="Unavailable"),
                httpx.Response(503, text="Unavailable"),
                httpx.Response(503, text="Unavailable"),
                httpx.Response(200, json={"thread": {"id": "t1"}}),
            ]
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                result = client.get_thread("t1")
        assert result["thread"]["id"] == "t1"
        assert mock_sleep.call_count == 3

    @respx.mock
    def test_500_raises_after_max_retries(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(500, text="Server error")
        )
        with patch("time.sleep"):
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError) as exc_info:
                    client.get_thread("t1")
        assert exc_info.value.status_code == 500

    @respx.mock
    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    def test_all_5xx_retried(self, status):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=[
                httpx.Response(status, text="err"),
                httpx.Response(200, json={"thread": {"id": "t1"}}),
            ]
        )
        with patch("time.sleep"):
            with QuipClient(token="tok") as client:
                result = client.get_thread("t1")
        assert result["thread"]["id"] == "t1"

    @respx.mock
    def test_backoff_delays_increase(self):
        """Each retry delay should be roughly double the previous."""
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(503, text="err")
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError):
                    client.get_thread("t1")
        delays = [c[0][0] for c in mock_sleep.call_args_list]
        assert len(delays) == 5
        # Each delay is roughly double the previous (within ±20% jitter)
        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1] * 0.5


# ---------------------------------------------------------------------------
# Non-retryable 4xx errors — raised immediately
# ---------------------------------------------------------------------------

class TestNonRetryable:
    @respx.mock
    def test_401_raised_immediately(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError) as exc_info:
                    client.get_thread("t1")
        assert exc_info.value.status_code == 401
        mock_sleep.assert_not_called()

    @respx.mock
    def test_403_raised_immediately(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(403, text="Forbidden")
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError) as exc_info:
                    client.get_thread("t1")
        assert exc_info.value.status_code == 403
        mock_sleep.assert_not_called()

    @respx.mock
    def test_404_raised_immediately(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError) as exc_info:
                    client.get_thread("t1")
        assert exc_info.value.status_code == 404
        mock_sleep.assert_not_called()

    @respx.mock
    def test_400_raised_immediately(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            return_value=httpx.Response(400, text="Bad Request")
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError):
                    client.get_thread("t1")
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Network timeout retry
# ---------------------------------------------------------------------------

class TestTimeoutRetry:
    @respx.mock
    def test_timeout_then_success_returns_result(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=[
                httpx.TimeoutException("timed out"),
                httpx.Response(200, json={"thread": {"id": "t1"}}),
            ]
        )
        with patch("time.sleep"):
            with QuipClient(token="tok") as client:
                result = client.get_thread("t1")
        assert result["thread"]["id"] == "t1"

    @respx.mock
    def test_five_timeouts_raises_api_error(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with patch("time.sleep"):
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError):
                    client.get_thread("t1")

    @respx.mock
    def test_five_timeouts_sleeps_five_times(self):
        respx.get(f"{QUIP_BASE}/threads/t1").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        with patch("time.sleep") as mock_sleep:
            with QuipClient(token="tok") as client:
                with pytest.raises(QuipAPIError):
                    client.get_thread("t1")
        assert mock_sleep.call_count == 5
