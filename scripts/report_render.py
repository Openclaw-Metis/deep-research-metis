"""Deliverable rendering function group.

Rendering turns the verified Markdown report into one self-contained HTML file:
every text node is escaped, only http(s) links survive, and no external asset,
font, or script is referenced. Writing the deliverable is the one effect in this
skill that requires an approval record, and an existing file is never replaced
unless the caller explicitly asks for it.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from research_store import (
    CITATION_MARK,
    FENCE,
    SemanticError,
    bibliography_entry_number,
    bilingual_length,
    citation_numbers,
    digest,
    find_bibliography,
    read_report,
    require,
    resolve_inside,
    resolve_run_dir,
    write_text_atomic,
)

HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")
LIST_ITEM = re.compile(r"^\s*[-*+]\s+(.*)$")
ORDERED_ITEM = re.compile(r"^\s*\d+[.)]\s+(.*)$")
TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_DIVIDER = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
ENTRY_MARKER = re.compile(r"^\s*(?:[-*+]\s+)?(?:[\[［【]\s*\d{1,3}\s*[\]］】]|\d{1,3}[.)、])\s*")
INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
# Quotes stay out of the match: they survive html.escape(quote=False) and would
# otherwise close the href attribute built from this text.
BARE_URL = re.compile(r"""(?<!["'>=])https?://[^\s<>"'`)）］】」』，。；、]*[^\s<>"'`)）］】」』，。；、.,;:!?]""")
DEFAULT_FOOTERS = {
    "zh-TW": "本報告由 deep-research-metis 產出，已通過結構、引用與支撐度檢查。支撐度檢查比對字詞與數字，不等同語意查證。",
    "en": "Generated with deep-research-metis. Structure, citation and claim-support checks passed; claim support compares wording and figures and is not a semantic review.",
}

PAGE_STYLE = """
:root { color-scheme: light dark; --ink: #16202b; --muted: #5a6b7c; --line: #d7dee6; --bg: #ffffff; --accent: #1f5f8b; }
@media (prefers-color-scheme: dark) { :root { --ink: #e7edf3; --muted: #a5b3c0; --line: #2c3946; --bg: #121820; --accent: #7fb5da; } }
body { background: var(--bg); color: var(--ink); font-family: "Noto Sans TC", "Microsoft JhengHei", system-ui, sans-serif; line-height: 1.75; margin: 0 auto; max-width: 46rem; padding: 3rem 1.25rem 5rem; }
h1, h2, h3 { line-height: 1.35; margin: 2.2rem 0 0.8rem; }
h1 { font-size: 1.9rem; border-bottom: 2px solid var(--accent); padding-bottom: 0.6rem; }
h2 { font-size: 1.4rem; color: var(--accent); }
p, li { font-size: 1rem; }
sup a { color: var(--accent); text-decoration: none; font-size: 0.75em; }
blockquote { border-left: 3px solid var(--line); color: var(--muted); margin: 1.2rem 0; padding: 0.2rem 1rem; }
table { border-collapse: collapse; display: block; overflow-x: auto; width: 100%; }
th, td { border: 1px solid var(--line); padding: 0.5rem 0.7rem; text-align: left; }
code { background: rgba(127, 181, 218, 0.16); border-radius: 4px; padding: 0.1rem 0.35rem; }
pre { background: rgba(127, 181, 218, 0.12); border-radius: 8px; overflow-x: auto; padding: 1rem; }
.ref { margin: 0.35rem 0; overflow-wrap: anywhere; }
footer { border-top: 1px solid var(--line); color: var(--muted); font-size: 0.85rem; margin-top: 3rem; padding-top: 1rem; }
"""

VERIFICATION_ARTIFACTS = (
    "structure_check.json",
    "citation_map.json",
    "claim_support.json",
)


def _require_current_verification(run_dir, report: str) -> dict[str, str]:
    """Require all delivery gates to be PASS for this exact report revision."""
    expected_digest = "sha256:" + digest(report)
    verified: dict[str, str] = {}
    for name in VERIFICATION_ARTIFACTS:
        path = run_dir / name
        if not path.is_file():
            raise SemanticError("render.verification-missing", "missing verification artifact: " + name)
        try:
            artifact = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SemanticError("render.verification-invalid", "invalid verification artifact: " + name) from exc
        if artifact.get("status") != "PASS":
            raise SemanticError("render.verification-failed", "verification artifact is not PASS: " + name)
        if artifact.get("report_digest") != expected_digest:
            raise SemanticError("render.verification-stale", "verification artifact is stale: " + name)
        verified[name] = expected_digest
    return verified


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = INLINE_CODE.sub(lambda match: "<code>" + match.group(1) + "</code>", escaped)
    escaped = BOLD.sub(lambda match: "<strong>" + match.group(1) + "</strong>", escaped)
    escaped = LINK.sub(
        lambda match: '<a href="' + match.group(2).replace('"', "&quot;") + '" rel="noreferrer">' + match.group(1) + "</a>",
        escaped,
    )
    escaped = BARE_URL.sub(lambda match: '<a href="' + match.group(0) + '" rel="noreferrer">' + match.group(0) + "</a>", escaped)
    return CITATION_MARK.sub(_citation_links, escaped)


def _citation_links(match: re.Match[str]) -> str:
    return "".join(
        '<sup><a href="#ref-' + str(number) + '">[' + str(number) + "]</a></sup>"
        for number in citation_numbers(match.group(0))
    )


def _bibliography_entry(line: str) -> str:
    """Render one entry with the anchor inline citations point at."""
    number = bibliography_entry_number(line)
    body = _inline(ENTRY_MARKER.sub("", line.strip()))
    if number is None:
        return '<p class="ref">' + body + "</p>"
    return '<p class="ref" id="ref-' + str(number) + '">[' + str(number) + "] " + body + "</p>"


def _render_blocks(report: str) -> tuple[list[str], int]:
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_tag = "ul"
    table_rows: list[list[str]] = []
    in_fence = False
    code_lines: list[str] = []
    heading_count = 0
    _, bibliography = find_bibliography(report)

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + _inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            blocks.append("<" + list_tag + ">" + "".join("<li>" + item + "</li>" for item in list_items) + "</" + list_tag + ">")
            list_items.clear()

    def flush_table() -> None:
        if table_rows:
            header, *body = table_rows
            head = "<tr>" + "".join("<th>" + cell + "</th>" for cell in header) + "</tr>"
            rows = "".join("<tr>" + "".join("<td>" + cell + "</td>" for cell in row) + "</tr>" for row in body)
            blocks.append("<table><thead>" + head + "</thead><tbody>" + rows + "</tbody></table>")
            table_rows.clear()

    for index, line in enumerate(report.splitlines()):
        if FENCE.match(line):
            in_fence = not in_fence
            if not in_fence:
                blocks.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
            else:
                flush_paragraph()
                flush_list()
                flush_table()
            continue
        if in_fence:
            code_lines.append(line)
            continue
        if index in bibliography:
            flush_paragraph()
            flush_list()
            flush_table()
            blocks.append(_bibliography_entry(line))
            continue
        if TABLE_DIVIDER.match(line):
            continue
        table_match = TABLE_ROW.match(line)
        if table_match:
            flush_paragraph()
            flush_list()
            table_rows.append([_inline(cell.strip()) for cell in table_match.group(1).split("|")])
            continue
        flush_table()
        heading = HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)), 3)
            heading_count += 1
            blocks.append("<h" + str(level) + ">" + _inline(heading.group(2).strip()) + "</h" + str(level) + ">")
            continue
        ordered = ORDERED_ITEM.match(line)
        unordered = LIST_ITEM.match(line)
        if ordered or unordered:
            flush_paragraph()
            wanted = "ol" if ordered else "ul"
            if list_items and wanted != list_tag:
                flush_list()
            list_tag = wanted
            list_items.append(_inline((ordered or unordered).group(1)))
            continue
        flush_list()
        if line.strip().startswith(">"):
            flush_paragraph()
            blocks.append("<blockquote>" + _inline(line.strip().lstrip("> ")) + "</blockquote>")
            continue
        if not line.strip():
            flush_paragraph()
            continue
        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()
    flush_table()
    return blocks, heading_count


def render_html(payload: dict[str, Any]) -> dict[str, Any]:
    """Render the verified report into one escaped, self-contained HTML deliverable."""
    run_dir = resolve_run_dir(payload, create=False)
    report = read_report(payload, run_dir)
    verification = _require_current_verification(run_dir, report)
    title = require(payload, "title", "render.title-required")
    output_path = resolve_inside(run_dir, payload.get("output_path", "report.html"), "render.output-inside-workspace")
    if output_path.suffix.lower() != ".html":
        raise SemanticError("render.output-extension", "output_path must end with .html")
    if output_path.exists() and not payload.get("overwrite", False):
        raise SemanticError("render.output-exists", "output already exists; pass overwrite=true to replace it")

    blocks, heading_count = _render_blocks(report)
    if heading_count == 0:
        raise SemanticError("render.no-heading", "the report has no heading to render")
    language = payload.get("language", "zh-TW")
    document = (
        "<!doctype html>\n<html lang=\"" + html.escape(language, quote=True) + "\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>" + html.escape(title, quote=False) + "</title>\n"
        "<style>" + PAGE_STYLE + "</style>\n</head>\n<body>\n"
        + "\n".join(blocks)
        + "\n<footer>" + html.escape(payload.get("footer", DEFAULT_FOOTERS.get(language, DEFAULT_FOOTERS["zh-TW"])), quote=False)
        + "</footer>\n</body>\n</html>\n"
    )
    write_text_atomic(output_path, document)
    return {
        "status": "OK",
        "output_path": str(output_path),
        "bytes": len(document.encode("utf-8")),
        "blocks": len(blocks),
        "measured_length": bilingual_length(report),
        "self_contained": True,
        "report_digest": "sha256:" + digest(report),
        "verification_artifacts": sorted(verification),
    }
