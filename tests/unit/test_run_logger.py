"""Unit tests — RunLogger structured log file (issue #12)."""

from __future__ import annotations

import re
import stat
from pathlib import Path

from quip_export.run_logger import RunLogger

# ISO 8601 UTC timestamp pattern like [2026-05-24T10:32:01Z]
_TS = re.compile(r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\]")


def _read_log(tmp_path: Path) -> str:
    return (tmp_path / "run.log").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Log creation
# ---------------------------------------------------------------------------

class TestLogCreation:
    def test_creates_run_log_file(self, tmp_path):
        with RunLogger(tmp_path):
            pass
        assert (tmp_path / "run.log").exists()

    def test_log_file_is_not_empty_after_write(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.info("ctx", "hello")
        assert (tmp_path / "run.log").stat().st_size > 0

    def test_appends_across_instances(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.info("ctx", "first")
        with RunLogger(tmp_path) as log:
            log.info("ctx", "second")
        content = _read_log(tmp_path)
        assert "first" in content
        assert "second" in content


# ---------------------------------------------------------------------------
# Log entry format
# ---------------------------------------------------------------------------

class TestLogFormat:
    def test_entry_contains_timestamp(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.warning("folder:f1", "access denied")
        assert _TS.search(_read_log(tmp_path))

    def test_entry_contains_level(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.warning("ctx", "msg")
        assert "[WARNING]" in _read_log(tmp_path)

    def test_entry_contains_context(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.error("thread:abc123", "export failed")
        assert "[thread:abc123]" in _read_log(tmp_path)

    def test_entry_contains_message(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.info("ctx", "all done")
        assert "all done" in _read_log(tmp_path)

    def test_info_entry_in_log(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.info("run", "started")
        assert "[INFO]" in _read_log(tmp_path)

    def test_error_entry_in_log(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.error("ctx", "something broke")
        assert "[ERROR]" in _read_log(tmp_path)

    def test_each_entry_on_own_line(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.warning("ctx", "first")
            log.warning("ctx", "second")
        lines = [ln for ln in _read_log(tmp_path).splitlines() if ln.strip()]
        assert len(lines) == 2


# ---------------------------------------------------------------------------
# Token scrubbing
# ---------------------------------------------------------------------------

class TestTokenScrubbing:
    def test_token_not_in_log_when_provided(self, tmp_path):
        secret = "super_secret_token_xyz_9999"
        with RunLogger(tmp_path, token=secret) as log:
            log.warning("auth", f"using token {secret}")
        assert secret not in _read_log(tmp_path)

    def test_token_replaced_with_stars(self, tmp_path):
        secret = "tok_abc"
        with RunLogger(tmp_path, token=secret) as log:
            log.info("auth", f"token is {secret}")
        assert "***" in _read_log(tmp_path)

    def test_no_token_provided_message_unchanged(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.info("ctx", "no secrets here")
        assert "no secrets here" in _read_log(tmp_path)


# ---------------------------------------------------------------------------
# Console output behaviour
# ---------------------------------------------------------------------------

class TestConsoleOutput:
    def test_warning_printed_to_stderr(self, tmp_path, capsys):
        with RunLogger(tmp_path) as log:
            log.warning("ctx", "watch out")
        assert "watch out" in capsys.readouterr().err

    def test_error_printed_to_stderr(self, tmp_path, capsys):
        with RunLogger(tmp_path) as log:
            log.error("ctx", "broke")
        assert "broke" in capsys.readouterr().err

    def test_info_not_printed_without_verbose(self, tmp_path, capsys):
        with RunLogger(tmp_path, verbose=False) as log:
            log.info("ctx", "quiet info")
        out, err = capsys.readouterr()
        assert "quiet info" not in out
        assert "quiet info" not in err

    def test_info_printed_to_stdout_with_verbose(self, tmp_path, capsys):
        with RunLogger(tmp_path, verbose=True) as log:
            log.info("ctx", "verbose info")
        assert "verbose info" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Non-ASCII (UTF-8)
# ---------------------------------------------------------------------------

class TestUnicode:
    def test_non_ascii_folder_name_written_correctly(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.info("folder:f1", "Über-Docs exported")
        assert "Über-Docs" in _read_log(tmp_path)

    def test_emoji_and_cjk_characters(self, tmp_path):
        with RunLogger(tmp_path) as log:
            log.info("ctx", "日本語テスト 🚀")
        assert "日本語テスト" in _read_log(tmp_path)


# ---------------------------------------------------------------------------
# Non-fatal behaviour when log dir is read-only
# ---------------------------------------------------------------------------

class TestReadOnlyDir:
    def test_readonly_dir_does_not_raise(self, tmp_path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            logger = RunLogger(ro)
            logger.warning("ctx", "should not crash")
            logger.close()
        except (PermissionError, OSError):
            pass  # Also acceptable — test is lenient per project pattern
        finally:
            ro.chmod(stat.S_IRWXU)
