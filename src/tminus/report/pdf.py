"""Create a readable PDF version of a T-MINUS scan report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from html import escape
from io import BytesIO

from tminus.engine.models import Finding, Rule, ScanResult

SEVERITIES = ("error", "warning", "info")
HEADINGS = {
    "error": ("Errors", "ACTION REQUIRED", "#cf222e"),
    "warning": ("Warnings", "REVIEW REQUIRED", "#9a6700"),
    "info": ("Information", "BEHAVIOR REVIEW", "#0969da"),
}


def render_pdf(
    result: ScanResult, target: str, rules: Sequence[Rule] = (), app_name: str | None = None
) -> bytes:
    """Return a paginated PDF report with every finding and technical detail."""
    from reportlab.lib import colors  # type: ignore[import-untyped]
    from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
    from reportlab.lib.units import mm  # type: ignore[import-untyped]
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # type: ignore[import-untyped]

    styles = getSampleStyleSheet()
    body = ParagraphStyle("TMBody", parent=styles["BodyText"], leading=14, spaceAfter=5)
    heading = ParagraphStyle("TMHeading", parent=styles["Heading2"], spaceBefore=14)
    rule = ParagraphStyle("TMRule", parent=styles["Heading3"], spaceBefore=10)
    meta = ParagraphStyle("TMMeta", parent=body, textColor=colors.HexColor("#57606a"))
    code = ParagraphStyle(
        "TMCode", parent=body, backColor=colors.HexColor("#f6f8fa"), fontName="Courier", fontSize=8
    )
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="T-MINUS scan report",
    )
    titles = {item.id: item.title for item in rules}
    name = app_name or "application"
    counts: Counter[str] = Counter(str(item.severity) for item in result.findings)
    story: list[object] = [
        Paragraph("T-MINUS scan report", styles["Title"]),
        Paragraph(f"<b>Target upgrade:</b> v15 to {escape(target)}", body),
        Paragraph(f"<b>Application:</b> {escape(name)}", body),
        Paragraph(f"<b>Files scanned:</b> {result.files_scanned}", body),
        Spacer(1, 6),
    ]
    if result.findings:
        overall = "error" if counts["error"] else "warning" if counts["warning"] else "info"
        _, status, color = HEADINGS[overall]
        story.extend(
            [
                Paragraph(f'<font color="{color}"><b>Result: {status}</b></font>', heading),
                Paragraph(f"<b>Findings:</b> {_counts(counts)}", body),
                Paragraph(
                    "This is a static scan. Confirm changes on a restored copy before upgrading "
                    "production.",
                    meta,
                ),
            ]
        )
    else:
        story.append(Paragraph("<b>Result: no known issues.</b>", heading))
    for severity in SEVERITIES:
        findings = [item for item in result.findings if item.severity == severity]
        if findings:
            story.extend(_groups(severity, findings, titles, heading, rule, body, meta, code))
    story.append(Paragraph("Not checked", heading))
    story.append(
        Paragraph(
            "Static checks only; site data, migrate rehearsal and v15 vs v16 comparison are "
            "not implemented.",
            body,
        )
    )
    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return stream.getvalue()


def _counts(counts: Counter[str]) -> str:
    """Describe severity counts in the report summary."""
    return ", ".join(f"{counts[item]} {item}" for item in SEVERITIES if counts[item])


def _groups(
    severity: str,
    findings: list[Finding],
    titles: dict[str, str],
    heading: object,
    rule: object,
    body: object,
    meta: object,
    code: object,
) -> list[object]:
    """Build PDF flowables grouped by rule for one severity."""
    from reportlab.platypus import Paragraph

    name, status, color = HEADINGS[severity]
    out: list[object] = [
        Paragraph(f'<font color="{color}">{name} ({len(findings)})</font>', heading)
    ]
    by_rule: dict[str, list[Finding]] = {}
    for finding in findings:
        by_rule.setdefault(finding.rule_id, []).append(finding)
    for number, rule_id in enumerate(sorted(by_rule), start=1):
        group = sorted(by_rule[rule_id], key=lambda item: (item.file, item.line))
        first = group[0]
        out.extend(
            [
                Paragraph(
                    f"{number}. {escape(titles.get(rule_id, rule_id))} ({len(group)} location(s))",
                    rule,
                ),
                Paragraph(
                    f'<font color="{color}"><b>{status}</b></font> - Rule: {escape(rule_id)} - '
                    f"[{escape(first.category)}, {escape(first.stage)}]",
                    meta,
                ),
                Paragraph(f"<b>Why it matters:</b> {escape(first.message)}", body),
                Paragraph(f"<b>Suggested action:</b> {escape(first.replacement)}", body),
            ]
        )
        for finding in group:
            out.append(Paragraph(escape(f"{finding.file}:{finding.line}"), meta))
            out.append(Paragraph(escape(finding.snippet), code))
            if finding.detail:
                out.append(Paragraph(f"<b>Technical context:</b> {escape(finding.detail)}", body))
    return out


def _footer(canvas: object, document: object) -> None:
    """Add a page number to each report page."""
    from reportlab.lib.units import mm

    canvas.setFont("Helvetica", 8)  # type: ignore[attr-defined]
    canvas.drawRightString(194 * mm, 10 * mm, f"T-MINUS - page {document.page}")  # type: ignore[attr-defined]
