"""CLI entry point for quip-export."""

from __future__ import annotations

import signal
import sys
from collections import Counter
from pathlib import Path
from typing import Annotated, Optional

import typer

from quip_export.auth import QuipAuthError, resolve_token
from quip_export.client import QuipAPIError, QuipClient
from quip_export.discovery import discover_folders, list_and_classify
from quip_export.exporter import OutputFormat, export_classified_thread, export_thread
from quip_export.fs import create_directory_structure
from quip_export.models import DuplicateRecord
from quip_export.run_logger import RunLogger
from quip_export.tracking import StateTracker, write_duplicates_report

app = typer.Typer(name="quip-export", help="Export Quip documents to files.")


def _parse_formats(raw: list[str]) -> list[OutputFormat]:
    valid = {f.value for f in OutputFormat}
    result = []
    for r in raw:
        if r not in valid:
            choices = ", ".join(valid)
            raise typer.BadParameter(f"'{r}' is not a valid format. Choose from: {choices}")
        result.append(OutputFormat(r))
    return result or list(OutputFormat)


@app.command()
def export(
    thread_ids: Annotated[list[str], typer.Argument(help="Quip thread ID(s) to export")],
    output: Annotated[Path, typer.Option(help="Output directory")] = Path("."),
    formats: Annotated[Optional[list[str]], typer.Option(help="Formats: md, docx, pdf")] = None,  # noqa: UP045
    token: Annotated[Optional[str], typer.Option(help="Quip API token (or set QUIP_TOKEN)")] = None,  # noqa: UP045
) -> None:
    """Export one or more Quip threads to the specified formats."""
    fmt_list = _parse_formats(formats or [])

    try:
        with QuipClient(token=token) as client:
            for tid in thread_ids:
                typer.echo(f"Exporting {tid}...")
                paths = export_thread(client, tid, output, fmt_list)
                for p in paths:
                    typer.echo(f"  -> {p}")
    except QuipAuthError as e:
        typer.echo(f"Auth error: {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def sync(
    output: Annotated[Path, typer.Option(help="Output directory")] = Path("."),
    token: Annotated[Optional[str], typer.Option(help="Quip API token (or set QUIP_TOKEN)")] = None,  # noqa: UP045
    verbose: Annotated[bool, typer.Option(help="Show INFO events on stdout")] = False,
    dry_run: Annotated[bool, typer.Option(help="Preview sync without writing any files")] = False,
) -> None:
    """Sync entire Quip workspace to a local directory tree.

    Exit codes: 0 = full success, 1 = partial failure, 2 = fatal error.
    """
    # ------------------------------------------------------------------
    # 1. Resolve token
    # ------------------------------------------------------------------
    try:
        resolved_token = resolve_token(flag_token=token)
    except QuipAuthError as exc:
        typer.echo(f"Auth error: {exc}", err=True)
        raise typer.Exit(2) from None

    # ------------------------------------------------------------------
    # 2. Prepare output directory and state machinery (skipped for dry-run)
    # ------------------------------------------------------------------
    logger: RunLogger | None = None
    tracker: StateTracker | None = None

    if not dry_run:
        try:
            output.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            typer.echo(f"Cannot create output directory {output}: {exc}", err=True)
            raise typer.Exit(2) from None

        logger = RunLogger(output, verbose=verbose, token=resolved_token)
        tracker = StateTracker(output)
        logger.info("sync", f"Run started — output: {output.resolve()}")

    # ------------------------------------------------------------------
    # 3. Ctrl+C handler
    # ------------------------------------------------------------------
    def _on_interrupt(sig: int, frame: object) -> None:
        if logger:
            logger.info("sync", "Run interrupted by user")
        sys.exit(2)

    signal.signal(signal.SIGINT, _on_interrupt)

    # ------------------------------------------------------------------
    # 4. Discover folder tree
    # ------------------------------------------------------------------
    typer.echo("Discovering folders...")
    try:
        with QuipClient(token=resolved_token) as client:
            tree = discover_folders(client)
    except (QuipAPIError, QuipAuthError) as exc:
        msg = f"Discovery failed: {exc}"
        typer.echo(msg, err=True)
        if logger:
            logger.error("sync", msg)
        raise typer.Exit(2) from None

    if tracker:
        tracker.record_folders(tree)
        tracker.update_stage("classifying")
    if logger:
        logger.info("sync", f"Discovered {len(tree.index)} folders")

    typer.echo(f"  {len(tree.index)} folder(s) found.")

    # ------------------------------------------------------------------
    # 5. Classify threads
    # ------------------------------------------------------------------
    typer.echo("Classifying threads...")
    try:
        with QuipClient(token=resolved_token) as client:
            threads = list_and_classify(client, tree)
    except (QuipAPIError, QuipAuthError) as exc:
        msg = f"Classification failed: {exc}"
        typer.echo(msg, err=True)
        if logger:
            logger.error("sync", msg)
        raise typer.Exit(2) from None

    if tracker:
        for t in threads:
            tracker.record_thread(t)
        tracker.update_stage("exporting")
    if logger:
        logger.info("sync", f"Classified {len(threads)} threads")

    typer.echo(f"  {len(threads)} thread(s) classified.")

    # ------------------------------------------------------------------
    # 6. Dry-run: print summary and exit
    # ------------------------------------------------------------------
    if dry_run:
        _print_dry_run_summary(tree, threads, output)
        raise typer.Exit(0)

    # ------------------------------------------------------------------
    # 7. Create local directory structure
    # ------------------------------------------------------------------
    folder_path_map = create_directory_structure(tree, output)

    # ------------------------------------------------------------------
    # 8. Export all threads
    # ------------------------------------------------------------------
    typer.echo("Exporting threads...")
    duplicate_records: list[DuplicateRecord] = []
    exported = 0
    failed = 0

    with QuipClient(token=resolved_token) as client:
        for thread in threads:
            try:
                data = client.get_thread(thread.thread_id)
                html: str = data.get("html", "")
                dup_rec = export_classified_thread(thread, html, folder_path_map)
                if dup_rec is not None:
                    duplicate_records.append(dup_rec)
                exported += 1
                if tracker:
                    for fid in thread.folder_ids:
                        if fid in folder_path_map:
                            tracker.record_export(thread.thread_id, folder_path_map[fid], "ok")
                if logger:
                    logger.info(f"thread:{thread.thread_id}", f"exported '{thread.title}'")
            except Exception as exc:
                failed += 1
                msg = f"Export failed for '{thread.title}': {exc}"
                if logger:
                    logger.warning(f"thread:{thread.thread_id}", msg)
                if tracker:
                    tracker.record_export(thread.thread_id, Path("(failed)"), "failed")

    # ------------------------------------------------------------------
    # 9. Write duplicates report
    # ------------------------------------------------------------------
    write_duplicates_report(duplicate_records, output, logger=logger)

    # ------------------------------------------------------------------
    # 10. Finish
    # ------------------------------------------------------------------
    if tracker:
        tracker.update_stage("done")

    summary = (
        f"Done — {exported} exported, {failed} failed, "
        f"{len(duplicate_records)} duplicate(s)."
    )
    typer.echo(summary)

    if logger:
        logger.info("sync", summary)
        logger.close()

    raise typer.Exit(1 if failed else 0)


def _print_dry_run_summary(tree: object, threads: list, output: Path) -> None:
    type_counts: Counter[str] = Counter(t.thread_class for t in threads)
    duplicate_count = sum(1 for t in threads if len(t.folder_ids) > 1)
    estimated_exports = sum(len(t.folder_ids) for t in threads)

    typer.echo("\nDry-run summary (no files written):")
    typer.echo(f"  Would export to: {output.resolve()}")
    typer.echo(f"  Folders discovered: {len(tree.index)}")  # type: ignore[attr-defined]
    typer.echo(f"  Threads found: {len(threads)}")
    for cls, count in sorted(type_counts.items()):
        typer.echo(f"    {cls}: {count}")
    typer.echo(f"  Estimated exports (incl. duplicates): {estimated_exports}")
    typer.echo(f"  Threads in multiple folders: {duplicate_count}")
