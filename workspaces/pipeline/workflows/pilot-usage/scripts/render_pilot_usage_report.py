"""Render validated two-page HTML with verified Example font assets, then print and verify the PDF with headless Chromium.

Called by build_pilot_usage_report.py. The PDF output is replaced only after the candidate passes every
check: policy page count, every media box equal to the policy page size, both Example font tokens embedded,
and the title/author metadata this module stamps with pypdf. Chromium is the only renderer: the
embedded-font detection reads the Type3 font descriptors Chromium writes for variable WOFF2 fonts.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter

from compute_pilot_usage_report import validate_computed_pilot_usage_report
from pilot_usage_shared import FONT_OUTPUT_DIRECTORY, ensure_font_assets, require_local_only_output_path

# Pilots with up to this many elapsed days chart beside the user table; longer ones take a
# full-width row below so page 1 keeps its two-column balance. The bar heights below and the
# `.chart-row`/`.chart-wide` CSS heights are the two sides of that layout.
DAILY_CHART_SIDE_MAX_DAYS = 16
DAILY_CHART_SIDE_BAR_PX = 58
DAILY_CHART_WIDE_BAR_PX = 76
POINTS_PER_INCH = 72


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _format_date(value: str, include_year: bool = True) -> str:
    parsed = date.fromisoformat(value)
    rendered = f"{parsed.strftime('%b')} {parsed.day}"
    return f"{rendered}, {parsed.year}" if include_year else rendered


def _format_date_range(start: str, end: str, include_year: bool = True) -> str:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if start_date.year == end_date.year and start_date.month == end_date.month:
        suffix = f", {end_date.year}" if include_year else ""
        return f"{start_date.strftime('%b')} {start_date.day}–{end_date.day}{suffix}"
    if start_date.year == end_date.year:
        suffix = f", {end_date.year}" if include_year else ""
        return f"{start_date.strftime('%b')} {start_date.day} – {end_date.strftime('%b')} {end_date.day}{suffix}"
    return f"{_format_date(start, include_year)} – {_format_date(end, include_year)}"


def _format_number(value: int) -> str:
    return f"{value:,}"


def _render_user_rows(users: list[dict[str, Any]], max_rows: int) -> str:
    """Name the top `max_rows` users by credits; fold the rest into one Other row (page 1 is fixed height)."""
    rows: list[str] = []
    for user in users[:max_rows]:
        muted = " muted" if user["task_count"] == 0 else ""
        rows.append(
            '<tr class="user-row{muted}"><td>{name}</td><td>{tasks}</td>'
            "<td>{week_one}</td><td>{week_two}</td><td>{credits}</td></tr>".format(
                muted=muted,
                name=_escape(user["display_name"]),
                tasks=user["task_count"],
                week_one=user["week_one_tasks"],
                week_two=user["week_two_tasks"],
                credits=_format_number(user["credits"]),
            )
        )
    folded = users[max_rows:]
    if folded:
        idle = sum(1 for user in folded if user["task_count"] == 0)
        idle_note = f", {idle} with no tasks" if idle else ""
        rows.append(
            '<tr class="user-row"><td>{name}</td><td>{tasks}</td>'
            "<td>{week_one}</td><td>{week_two}</td><td>{credits}</td></tr>".format(
                name=_escape(f"Other ({_plural(len(folded), 'seat', 'seats')}{idle_note})"),
                tasks=sum(user["task_count"] for user in folded),
                week_one=sum(user["week_one_tasks"] for user in folded),
                week_two=sum(user["week_two_tasks"] for user in folded),
                credits=_format_number(sum(user["credits"] for user in folded)),
            )
        )
    return "".join(rows)


def _day_label(day: date, first: bool) -> str:
    """Day number, with the month named on the first bar and on each first of month."""
    if first or day.day == 1:
        return f"{day.day}<br>{day.strftime('%b')}"
    return str(day.day)


def _render_daily_bars(computed_report: dict[str, Any]) -> str:
    daily_tasks = computed_report["daily_tasks"]
    maximum = max((row["task_count"] for row in daily_tasks), default=0)
    wide = len(daily_tasks) > DAILY_CHART_SIDE_MAX_DAYS
    bar_scale = DAILY_CHART_WIDE_BAR_PX if wide else DAILY_CHART_SIDE_BAR_PX
    bars: list[str] = []
    for index, row in enumerate(daily_tasks):
        height = (
            max(4, round(row["task_count"] / maximum * bar_scale))
            if row["task_count"]
            else 2
        )
        color_class = " peak" if maximum and row["task_count"] == maximum else ""
        bars.append(
            '<div class="day"><span class="bar-value">{value}</span>'
            '<div class="bar{color}" style="height:{height}px"></div>'
            '<span class="day-label">{day}</span></div>'.format(
                value=row["task_count"],
                color=color_class,
                height=height,
                day=_day_label(date.fromisoformat(row["date"]), index == 0),
            )
        )
    return f'<div class="chart-row">{"".join(bars)}</div>'


def _render_labeled_bullets(items: list[dict[str, str]]) -> str:
    return "".join(
        f"<li><strong>{_escape(item['label'])}.</strong> {_escape(item['text'])}</li>"
        for item in items
    )


def _plural(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _font_relative_url(policy: dict[str, Any], role: str) -> str:
    file_name = policy["fonts"][role]["file_name"]
    return (FONT_OUTPUT_DIRECTORY / file_name).as_posix()


def _render_pilot_usage_report_html(computed_report: dict[str, Any], policy: dict[str, Any]) -> str:
    report = computed_report["report"]
    report_title = computed_report["report_title"]
    headline = computed_report["headline"]
    periods = computed_report["periods"]
    narratives = computed_report["reviewed_narratives"]
    highlights = computed_report["computed_highlights"]
    users_by_id = {user["user_id"]: user for user in computed_report["users"]}
    most_consistent_id = highlights["most_consistent_user_id"]
    most_consistent = users_by_id.get(most_consistent_id) if most_consistent_id else None
    uncategorized_id = policy["uncategorized_category_id"]
    fonts = policy["fonts"]
    page_width_in = policy["page_width_points"] / POINTS_PER_INCH
    page_height_in = policy["page_height_points"] / POINTS_PER_INCH

    computed_bullets = [
        {
            "label": "Consumption by top users",
            "text": (
                f"The top {highlights['top_user_count']} users account for "
                f"~{highlights['top_user_credit_share_percent']}% of consumption"
            ),
        }
    ]
    if most_consistent:
        computed_bullets.append(
            {
                "label": "Most first-billing dates",
                "text": (
                    f"{most_consistent['display_name']}: contexts first billed on "
                    f"{most_consistent['active_days']} of {headline['elapsed_days']} days "
                    f"({most_consistent['task_count']} billed contexts)"
                ),
            }
        )
    computed_bullets.extend(narratives["usage_highlights"])
    computed_bullets.append(
        {
            "label": "Granted less recorded consumption",
            "text": (
                f"{_format_number(headline['remaining_credits'])} of "
                f"{_format_number(headline['granted_credits'])} granted credits are unconsumed by the recorded contexts; this is not a current available balance"
            ),
        }
    )

    participation_notes = " ".join(
        f"{_escape(user['display_name'])}: {_escape(user['participation_note'])}"
        for user in computed_report["users"]
        if user["participation_note"]
    )

    category_segments = "".join(
        '<span style="background:{color};width:{width}%"></span>'.format(
            color=_escape(category["color"]),
            width=category["share_percent_precise"],
        )
        for category in computed_report["categories"]
        if category["category_id"] != uncategorized_id
        if category["credits"] > 0
    )
    category_rows = "".join(
        '<div class="category-row"><span class="swatch" style="background:{color}"></span>'
        "<strong>{label}</strong><span>{tasks} contexts</span><span>{credits} cr</span>"
        "<b>{share}%</b><em>{description}</em></div>".format(
            color=_escape(category["color"]),
            label=_escape(category["label"]),
            tasks=category["task_count"],
            credits=_format_number(category["credits"]),
            share=category["share_percent"],
            description=_escape(category["description"]),
        )
        for category in computed_report["categories"]
    )
    uncategorized = next(
        (
            category
            for category in computed_report["categories"]
            if category["category_id"] == uncategorized_id
        ),
        None,
    )
    uncategorized_note = ""
    if uncategorized and uncategorized["task_count"]:
        uncategorized_note = (
            f"{_plural(uncategorized['task_count'], 'context', 'contexts')} "
            f"({_format_number(uncategorized['credits'])} credits, "
            f"{uncategorized['share_percent_precise']}%) are {uncategorized['label'].lower()}: "
            f"{uncategorized['description'].rstrip('.')}. "
        )

    representative_cards = "".join(
        '<article class="work-card"><h3>{title}</h3><span>{people}</span><p>{summary}</p></article>'.format(
            title=_escape(card["title"]),
            people=_escape(
                ", ".join(
                    users_by_id[user_id]["display_name"] for user_id in card["user_ids"]
                )
            ),
            summary=_escape(card["summary"]),
        )
        for card in narratives["representative_work"]
    )
    work_interpretation = "".join(
        f"<p>{_escape(paragraph)}</p>"
        for paragraph in narratives["work_interpretation"]
    )

    pilot_window = _format_date_range(report["pilot_start"], report["pilot_end"])
    through_range = _format_date_range(report["pilot_start"], report["data_through"])
    week_one_range = _format_date_range(
        periods["week_one_start"], periods["week_one_end"], include_year=False
    )
    week_two_range = (
        _format_date_range(periods["week_two_start"], periods["week_two_end"], include_year=False)
        if periods["week_two_start"]
        else "none yet"
    )
    chart_block = (
        f'<h2>Contexts first billed per day</h2><div class="chart">{_render_daily_bars(computed_report)}</div>'
        f'<p class="fineprint">{through_range}.</p>'
    )
    highlights_block = f'<div class="highlights"><h2>Usage highlights</h2><ul>{_render_labeled_bullets(computed_bullets)}</ul></div>'
    if len(computed_report["daily_tasks"]) <= DAILY_CHART_SIDE_MAX_DAYS:
        side_column = f"<div>{chart_block}{highlights_block}</div>"
        full_width_chart = ""
    else:
        side_column = f"<div>{highlights_block}</div>"
        full_width_chart = f'<div class="chart-wide">{chart_block}</div>'
    max_rows = policy["user_table_max_rows"]
    user_table_note = (
        f" Top {max_rows} users shown; the rest are combined in the Other row."
        if len(computed_report["users"]) > max_rows
        else ""
    )
    footer = (
        f"Prepared by {_escape(report['prepared_by'])}, {_escape(policy['metadata_author'])} &nbsp;·&nbsp; "
        f"{_escape(report['confidentiality_label'])}. For "
        f"{_escape(report['customer_name'])} internal use."
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_escape(policy["metadata_title"])}</title>
<meta name="author" content="{_escape(policy["metadata_author"])}">
<style>
@font-face{{font-family:"{_escape(fonts["sans"]["family"])}";src:url("{_font_relative_url(policy, "sans")}") format("truetype");font-style:normal;font-weight:100 900;font-display:block}}
@font-face{{font-family:"{_escape(fonts["mono"]["family"])}";src:url("{_font_relative_url(policy, "mono")}") format("truetype");font-style:normal;font-weight:100 900;font-display:block}}
:root{{--paper:#f7f7f4;--ink:#272621;--muted:#777770;--line:#d9d6cf;--teal:#00717a;--soft:#e8f0ef}}
*{{box-sizing:border-box}} html,body{{margin:0;background:#ecebe7;color:var(--ink);font-family:"{_escape(fonts["sans"]["family"])}",Arial,sans-serif}}
body{{font-size:11px;line-height:1.28}} .report-page{{position:relative;width:{page_width_in:g}in;height:{page_height_in:g}in;margin:18px auto;padding:.48in .5in .42in;background:var(--paper);overflow:hidden;page-break-after:always}}
.report-page:last-child{{page-break-after:auto}} .eyebrow{{font-size:11px;font-weight:800;letter-spacing:.01em;color:var(--teal)}}
h1{{font-size:29px;line-height:1.05;margin:5px 0 13px;letter-spacing:.01em}} h2{{font-size:15px;margin:0 0 8px}} h3{{margin:0;color:var(--teal);font-size:12px}}
.header{{border-bottom:1px solid var(--line);position:relative}} .header-meta{{position:absolute;right:0;top:-3px;text-align:right;color:var(--muted);font-family:"{_escape(fonts["mono"]["family"])}",monospace;font-size:12px;line-height:1.45}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:15px 0}} .metric{{border:1px solid var(--line);border-radius:8px;padding:12px 13px;height:90px;background:#fbfbf9}}
.metric b{{display:block;color:var(--teal);font-size:25px;line-height:1}} .metric strong{{display:block;margin-top:7px;font-size:11px}} .metric span{{display:block;color:var(--muted);margin-top:5px;font-size:9px}}
.scope-note{{border-left:4px solid var(--teal);padding:10px 13px;background:var(--soft);border-radius:0 7px 7px 0;margin:0 0 20px}} .scope-note strong{{display:block;margin-bottom:4px}}
.page-one-grid{{display:grid;grid-template-columns:minmax(0,58fr) minmax(0,42fr);gap:28px}} .section-title-note{{font-size:9px;color:var(--muted);font-weight:400;margin-left:8px}}
table{{border-collapse:collapse;width:100%;font-size:10px}} th{{background:#ebeae6;color:var(--muted);text-align:right;padding:4px 7px;font-size:9px}} th:first-child,td:first-child{{text-align:left}} td{{padding:3px 7px;text-align:right}} tr:nth-child(even){{background:#fbfbf9}} .user-row td:first-child{{font-weight:600}} .user-row.muted{{color:var(--muted)}} tfoot{{border-top:1px solid var(--line);font-weight:800}}
    .fineprint{{font-size:9px;color:var(--muted);margin-top:7px}} .chart{{display:flex;flex-direction:column;gap:7px;margin:12px 5px 4px}} .chart-row{{height:76px;display:flex;align-items:flex-end;gap:3px}} .day{{height:76px;min-width:0;flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center}} .bar-value{{font-size:7px;margin-bottom:2px}} .bar{{width:100%;max-width:13px;background:#79b5b9}} .bar.peak{{background:#218a91}} .day-label{{font-size:7px;color:var(--muted);margin-top:3px;white-space:nowrap}} .chart-wide{{margin-top:14px}} .chart-wide .chart{{margin:12px 0 4px}} .chart-wide .chart-row,.chart-wide .day{{height:110px}} .chart-wide .bar{{max-width:11px}} .chart-wide .day-label{{height:16px;line-height:8px;text-align:center}}
ul{{padding-left:17px;margin:4px 0}} li{{margin:0 0 7px}} li::marker{{color:var(--teal)}} .highlights{{margin-top:21px;font-size:10px}}
.footer{{position:absolute;bottom:.28in;left:.5in;right:.5in;border-top:1px solid var(--line);padding-top:7px;color:var(--muted);font-size:9px}}
.page-two h1{{font-size:27px;margin-bottom:15px}} .work-distribution{{margin-top:22px}} .stacked{{height:18px;display:flex;margin:10px 0 14px;overflow:hidden}} .stacked span{{display:block;height:100%}}
.category-row{{display:grid;grid-template-columns:14px 2.7fr .9fr 1fr .55fr 3fr;gap:8px;align-items:center;margin:0 0 12px}} .swatch{{width:11px;height:11px}} .category-row span:nth-of-type(n+2){{text-align:right}} .category-row b{{color:var(--teal);text-align:right}} .category-row em{{font-style:normal;color:var(--muted);font-size:9px}}
.work-grid{{display:grid;grid-template-columns:1fr 1fr;gap:13px 16px}} .work-card{{border:1px solid var(--line);border-radius:8px;background:#fbfbf9;padding:11px 13px;min-height:99px}} .work-card span{{display:block;color:var(--muted);font-size:9px;margin:3px 0 5px}} .work-card p{{margin:0}}
.bottom-grid{{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:20px}} .bottom-grid p{{margin:0 0 11px}}
@page{{size:{page_width_in:g}in {page_height_in:g}in;margin:0}} @media print{{html,body{{background:white}}.report-page{{margin:0}}}}
</style>
</head>
<body>
<section class="report-page page-one">
  <header class="header"><div class="eyebrow">{_escape(report_title)}</div><h1>{_escape(report["customer_name"])}</h1>
    <div class="header-meta">Prepared {_format_date(report["prepared_date"])}<br>Pilot window: {pilot_window}<br>Data through {_format_date(report["data_through"])} (Day {periods["pilot_day_number"]} of {periods["pilot_total_days"]})</div></header>
  <div class="cards">
    <div class="metric"><b>{headline["active_users"]} of {headline["seat_count"]}</b><strong>users active</strong><span>seats with billed tasks</span></div>
    <div class="metric"><b>{headline["task_count"]}</b><strong>billed task contexts</strong><span>first billed within this window</span></div>
    <div class="metric"><b>{_format_number(headline["credits_used"])}</b><strong>credits used</strong><span>across reviewed workspace scope</span></div>
    <div class="metric"><b>{headline["active_days"]} of {headline["elapsed_days"]}</b><strong>first-billing days</strong><span>days with a context first billed in the window</span></div>
  </div>
  <div class="scope-note"><strong>Scope.</strong> {_escape(narratives["scope_note"])}</div>
  <div class="page-one-grid"><div><h2>Usage by user <span class="section-title-note">(sorted by credits consumed)</span></h2>
    <table><thead><tr><th>USER</th><th>CONTEXTS</th><th>WK 1</th><th>AFTER</th><th>CREDITS</th></tr></thead><tbody>{_render_user_rows(computed_report["users"], max_rows)}</tbody>
    <tfoot><tr><td>Total ({headline["seat_count"]} seats)</td><td>{headline["task_count"]}</td><td></td><td></td><td>{_format_number(headline["credits_used"])}</td></tr></tfoot></table>
    <p class="fineprint">Wk 1 = {week_one_range}, After = {week_two_range}.{user_table_note}<br>{participation_notes}</p></div>
    {side_column}</div>{full_width_chart}
  <footer class="footer">Scope: Platform billed task contexts and credit consumption across all {headline["seat_count"]} seats, reviewed workspaces, {through_range}.<br>{footer} &nbsp;·&nbsp; Page 1 of 2</footer>
</section>
<section class="report-page page-two">
  <header class="header"><div class="eyebrow">{_escape(report_title)}</div><h1>What the team is evaluating</h1><div class="header-meta">{through_range}</div></header>
  <section class="work-distribution"><h2>Where the work went <span class="section-title-note">(all {headline["task_count"]} billed contexts, by share of credits consumed)</span></h2>
    <div class="stacked">{category_segments}</div>{category_rows}<p class="fineprint">{_escape(uncategorized_note)}Shares are of the {_format_number(headline["credits_used"])} credits consumed to date.</p></section>
  <section><h2 style="margin-top:21px">Representative work</h2><div class="work-grid">{representative_cards}</div></section>
  <div class="bottom-grid"><section><h2>What the pattern shows</h2>{work_interpretation}</section><section><h2>Potential business value</h2><ul>{_render_labeled_bullets(narratives["business_value"])}</ul></section></div>
  <footer class="footer">{_escape(narratives["source_note"])}<br>{footer} &nbsp;·&nbsp; Page 2 of 2</footer>
</section>
</body>
</html>
"""


def render_validated_pilot_usage_report_html(
    normalized_input: dict[str, Any], policy: dict[str, Any], computed_report: dict[str, Any]
) -> str:
    """Validate all deterministic fields, then return escaped two-page HTML."""
    problems = validate_computed_pilot_usage_report(
        normalized_input, policy, computed_report
    )
    if problems:
        raise ValueError("report validation failed: " + ", ".join(problems))
    return _render_pilot_usage_report_html(computed_report, policy)


def write_validated_pilot_usage_report_html(
    normalized_input: dict[str, Any], policy: dict[str, Any], computed_report: dict[str, Any], output_path: Path
) -> Path:
    """Write validated HTML and its integrity-checked relative font assets; return the HTML path."""
    output_path = require_local_only_output_path(output_path)
    rendered_html = render_validated_pilot_usage_report_html(
        normalized_input, policy, computed_report
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_font_assets(policy, output_path.parent / FONT_OUTPUT_DIRECTORY)
    output_path.write_text(rendered_html, encoding="utf-8")
    return output_path


# --- PDF printing and verification -------------------------------------------------------

# Headless Chromium advances virtual time this far so web fonts finish loading before print.
CHROMIUM_VIRTUAL_TIME_BUDGET_MS = 1000
CHROMIUM_CANDIDATES = ("chromium", "google-chrome", "chromium-browser")
PLAYWRIGHT_CHROMIUM_GLOB = ".cache/ms-playwright/chromium-*/chrome-linux*/chrome"


@dataclass(frozen=True)
class PilotUsagePdfInspection:
    page_count: int
    media_boxes: tuple[tuple[float, float], ...]
    title: str
    author: str
    embedded_font_tokens: tuple[str, ...]


def inspect_pilot_usage_pdf(
    pdf_path: Path, font_tokens: tuple[str, ...]
) -> PilotUsagePdfInspection:
    """Read page, metadata, and embedded-font invariants with a PDF parser."""
    reader = PdfReader(pdf_path)
    font_names: set[str] = set()
    media_boxes: list[tuple[float, float]] = []
    for page in reader.pages:
        media_boxes.append((float(page.mediabox.width), float(page.mediabox.height)))
        resources = page.get("/Resources")
        resources = resources.get_object() if resources is not None else {}
        font_resources = resources.get("/Font")
        font_resources = font_resources.get_object() if font_resources is not None else {}
        for font_reference in font_resources.values():
            font_object = font_reference.get_object()
            font_names.add(str(font_object.get("/BaseFont", "")))
            # Chromium embeds variable WOFF2 fonts as Type3 with the family on the descriptor only.
            descriptor = font_object.get("/FontDescriptor")
            if descriptor is not None:
                descriptor = descriptor.get_object()
                font_names.add(str(descriptor.get("/FontFamily", "")))
                font_names.add(str(descriptor.get("/FontName", "")))
    def normalized_font_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower()).replace("beta", "")

    embedded_tokens = tuple(
        token
        for token in font_tokens
        if any(
            normalized_font_name(token) in normalized_font_name(name)
            for name in font_names
        )
    )
    metadata = reader.metadata or {}
    return PilotUsagePdfInspection(
        page_count=len(reader.pages),
        media_boxes=tuple(media_boxes),
        title=str(metadata.get("/Title", "")),
        author=str(metadata.get("/Author", "")),
        embedded_font_tokens=embedded_tokens,
    )


def _write_pdf_metadata(
    source_path: Path, output_path: Path, title: str, author: str
) -> None:
    reader = PdfReader(source_path)
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.add_metadata({"/Title": title, "/Author": author, "/Creator": author})
    with output_path.open("wb") as output_file:
        writer.write(output_file)


def _pdf_render_command(
    renderer_binary: str,
    html_path: Path,
    pdf_path: Path,
) -> list[str]:
    if renderer_binary != "auto":
        resolved = shutil.which(renderer_binary)
        if resolved is None:
            raise RuntimeError(
                f"Chromium PDF tooling is unavailable: {renderer_binary}"
            )
        return _chromium_command(resolved, html_path, pdf_path)

    for candidate in CHROMIUM_CANDIDATES:
        resolved = shutil.which(candidate)
        if resolved is not None:
            return _chromium_command(resolved, html_path, pdf_path)
    for playwright_chrome in sorted(Path.home().glob(PLAYWRIGHT_CHROMIUM_GLOB)):
        if playwright_chrome.is_file():
            return _chromium_command(str(playwright_chrome), html_path, pdf_path)
    for mac_chrome in (Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
                       *sorted(Path.home().glob('Library/Caches/ms-playwright/chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'))):
        if mac_chrome.is_file():
            return _chromium_command(str(mac_chrome), html_path, pdf_path)
    raise RuntimeError(
        "PDF tooling is unavailable: no Chromium binary on PATH "
        f"({', '.join(CHROMIUM_CANDIDATES)}) or under ~/{PLAYWRIGHT_CHROMIUM_GLOB}"
    )


def _chromium_command(
    chromium_path: str,
    html_path: Path,
    pdf_path: Path,
) -> list[str]:
    return [
        chromium_path,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--allow-file-access-from-files",
        "--run-all-compositor-stages-before-draw",
        f"--virtual-time-budget={CHROMIUM_VIRTUAL_TIME_BUDGET_MS}",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path.resolve().as_uri(),
    ]


def _validate_inspection(
    inspection: PilotUsagePdfInspection, policy: dict[str, Any]
) -> None:
    problems: list[str] = []
    if inspection.page_count != policy["page_count"]:
        problems.append(
            f"expected {policy['page_count']} pages, got {inspection.page_count}"
        )
    expected_box = (
        float(policy["page_width_points"]),
        float(policy["page_height_points"]),
    )
    if len(inspection.media_boxes) != inspection.page_count:
        problems.append("each PDF page must declare a media box")
    if any(box != expected_box for box in inspection.media_boxes):
        problems.append(
            f"every PDF page must be {policy['page_size']} "
            f"({policy['page_width_points']} × {policy['page_height_points']} points)"
        )
    if inspection.title != policy["metadata_title"]:
        problems.append("PDF title metadata is incorrect")
    if inspection.author != policy["metadata_author"]:
        problems.append("PDF author metadata is incorrect")
    expected_tokens = tuple(
        font["pdf_name_token"] for font in policy["fonts"].values()
    )
    if set(inspection.embedded_font_tokens) != set(expected_tokens):
        families = " and ".join(font["family"] for font in policy["fonts"].values())
        problems.append(f"official {families} fonts are not both embedded")
    if problems:
        raise RuntimeError("; ".join(problems))


def print_pilot_usage_pdf(
    html_path: Path,
    output_path: Path,
    policy: dict[str, Any],
    chromium_binary: str = "auto",
    font_directory: Path | None = None,
) -> PilotUsagePdfInspection:
    """Print HTML, set metadata, verify page count, page size and embedded fonts, then replace the output."""
    output_path = require_local_only_output_path(output_path)
    if not html_path.is_file():
        raise RuntimeError(f"validated HTML is unavailable: {html_path}")
    resolved_font_directory = font_directory or (html_path.parent / FONT_OUTPUT_DIRECTORY)
    ensure_font_assets(policy, resolved_font_directory, download=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="pilot-usage-pdf-", dir=output_path.parent
    ) as temporary_directory:
        chromium_pdf = Path(temporary_directory) / "chromium.pdf"
        candidate_pdf = Path(temporary_directory) / "verified.pdf"
        command = _pdf_render_command(chromium_binary, html_path, chromium_pdf)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=True,
                timeout=policy["chromium_timeout_seconds"],
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("PDF generation timed out") from exc
        if completed.returncode != 0 or not chromium_pdf.is_file():
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"PDF generation failed: {detail}")
        _write_pdf_metadata(
            chromium_pdf,
            candidate_pdf,
            policy["metadata_title"],
            policy["metadata_author"],
        )

        font_tokens = tuple(
            font["pdf_name_token"] for font in policy["fonts"].values()
        )
        inspection = inspect_pilot_usage_pdf(candidate_pdf, font_tokens)
        _validate_inspection(inspection, policy)
        # Verified: only now does the previous output (if any) get replaced.
        candidate_pdf.replace(output_path)
    return inspection
