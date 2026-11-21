"""Command line entry point: `tminus scan <path> --target v16`."""

from __future__ import annotations

import sys
from enum import StrEnum
from pathlib import Path

import typer

from tminus import __version__
from tminus.engine.baseline import BaselineError, apply_baseline, load_baseline, write_baseline
from tminus.engine.env_check import check_environment, format_rows, run_command
from tminus.engine.loader import RuleLoadError, UnknownTargetError, load_rules, load_target
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


class ColorMode(StrEnum):
    """When the text report uses ANSI terminal colors."""

    auto = "auto"
    always = "always"
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
    baseline: Path | None = typer.Option(
        None, "--baseline", help="Hide findings already in this baseline (or JSON report)."
    ),
    save_baseline: Path | None = typer.Option(
        None, "--write-baseline", help="Save the current findings as a baseline and exit 0."
    ),
    color: ColorMode = typer.Option(
        ColorMode.auto, "--color", help="Color text output: auto, always or never."
    ),
) -> None:
    """T-30: static scan of code for breaking changes (read-only)."""
    if baseline is not None and save_baseline is not None:
        typer.echo("use either --baseline or --write-baseline, not both", err=True)
        raise typer.Exit(EXIT_USAGE)
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

    if save_baseline is not None:
        count = write_baseline(result, path, save_baseline, target)
        typer.echo(f"Wrote a baseline of {count} findings to {save_baseline}")
        return
    if baseline is not None:
        try:
            result = apply_baseline(result, load_baseline(baseline, path), path)
        except BaselineError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(EXIT_USAGE) from exc

    use_color = color == ColorMode.always or (color == ColorMode.auto and sys.stdout.isatty())
    report = (
        render_json(result, target)
        if fmt == OutputFormat.json
        else render_text(result, target, rules, app_name=path.name, color=use_color)
    )
    typer.echo(report, color=use_color)

    if fail_on is not FailOn.never:
        threshold = SEVERITY_ORDER[fail_on.value]
        if any(SEVERITY_ORDER[f.severity] >= threshold for f in result.findings):
            raise typer.Exit(EXIT_FINDINGS)


@app.command()
def env(
    path: Path = typer.Argument(Path("."), help="Bench folder (used to read its Python version)."),
    target: str = typer.Option(..., "--target", help="Version to check against, e.g. v16."),
) -> None:
    """T-30: compare Python, Node, MariaDB and Redis on this machine with what the target needs."""
    try:
        info = load_target(target)
    except UnknownTargetError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(EXIT_USAGE) from exc
    except RuleLoadError as exc:
        typer.echo(f"invalid target file: {exc}", err=True)
        raise typer.Exit(EXIT_FAILED) from exc
    rows = check_environment(info.requirements, run_command, path if path.is_dir() else None)
    typer.echo(format_rows(rows, target))
