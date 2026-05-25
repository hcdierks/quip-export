"""CLI entry point for quip-export."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from quip_export.client import QuipAuthError, QuipClient
from quip_export.exporter import OutputFormat, export_thread

app = typer.Typer(name="quip-export", help="Export Quip documents to files.")


def _parse_formats(raw: list[str]) -> list[OutputFormat]:
    valid = {f.value for f in OutputFormat}
    result = []
    for r in raw:
        if r not in valid:
            raise typer.BadParameter(f"'{r}' is not a valid format. Choose from: {', '.join(valid)}")
        result.append(OutputFormat(r))
    return result or list(OutputFormat)


@app.command()
def export(
    thread_ids: Annotated[list[str], typer.Argument(help="Quip thread ID(s) to export")],
    output_dir: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path("."),
    formats: Annotated[
        Optional[list[str]],
        typer.Option("--format", "-f", help="Output format(s): md, docx, pdf"),
    ] = None,
    token: Annotated[Optional[str], typer.Option("--token", help="Quip API token (or set QUIP_TOKEN)")] = None,
) -> None:
    """Export one or more Quip threads to the specified formats."""
    fmt_list = _parse_formats(formats or [])

    try:
        with QuipClient(token=token) as client:
            for tid in thread_ids:
                typer.echo(f"Exporting {tid}...")
                paths = export_thread(client, tid, output_dir, fmt_list)
                for p in paths:
                    typer.echo(f"  -> {p}")
    except QuipAuthError as e:
        typer.echo(f"Auth error: {e}", err=True)
        raise typer.Exit(1)
