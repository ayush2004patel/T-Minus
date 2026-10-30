"""Command line entry point: `tminus scan <path> --target v16`."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer

from tminus import __version__
from tminus.engine.loader import RuleLoadError, UnknownTargetError, load_rules
from tminus.engine.models import SEVERITY_ORDER
from tminus.engine.runner import scan_path
from tminus.report.render import render_json, render_text

app = typer.Typer(help="Count down to a clean Frappe/ERPNext upgrade.", no_args_is_help=True)

EXIT_FINDINGS = 1  # findings at or above --fail-on
EXIT_USAGE = 2  # unknown target, missing path
EXIT_FAILED = 3  # scan could not run


class OutputFormat(StrEnum):
    """Supported report formats."""

    text = "text"
    json = "json"


class FailOn(StrEnum):
    """Lowest severity that makes the command fail."""

    error = "error"
    warning = "warning"
    info = "info"
    never = "never"


def _version_callback(value: bool) -> None:
    """Print the version and exit when --version is given."""
    if value:
        typer.echo(f"tminus {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    """Root command group (keeps `scan` as a subcommand)."""


@app.command()
def scan(
    path: Path = typer.Argument(..., help="App folder or file to scan."),
    target: str = typer.Option(..., "--target", help="Version to check against, e.g. v16."),
    fmt: OutputFormat = typer.Option(OutputFormat.text, "--format", help="Report format."),
    fail_on: FailOn = typer.Option(FailOn.error, "--fail-on", help="Lowest severity that fails."),
) -> None:
    """T-30: static scan of code for breaking changes (read-only)."""
    try:
        rules = load_rules(target)
        result = scan_path(path, rules)
    except UnknownTargetError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(EXIT_USAGE) from exc
    except FileNotFoundError as exc:
        typer.echo(f"path not found: {exc}", err=True)
        raise typer.Exit(EXIT_USAGE) from exc
    except RuleLoadError as exc:  # a broken rule file is a tool bug, not a usage error
        typer.echo(f"invalid rule: {exc}", err=True)
        raise typer.Exit(EXIT_FAILED) from exc

    report = (
        render_json(result, target) if fmt is OutputFormat.json else render_text(result, target)
    )
    typer.echo(report)

    if fail_on is not FailOn.never:
        threshold = SEVERITY_ORDER[fail_on.value]
        if any(SEVERITY_ORDER[f.severity] >= threshold for f in result.findings):
            raise typer.Exit(EXIT_FINDINGS)
