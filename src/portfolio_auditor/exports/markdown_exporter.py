"""
exports/markdown_exporter.py

Generates a self-contained Markdown or HTML portfolio report from the
processed audit artifacts.

Design goals
------------
- Zero extra dependencies: uses only stdlib + the project's existing models.
- The HTML variant is a single file with inline CSS — no external assets.
- The report is human-readable and recruiter-shareable.
- Sections: executive summary, featured repos, improvement backlog,
  top actions, redundancy clusters, score distribution table.

Usage
-----
    from portfolio_auditor.exports.markdown_exporter import MarkdownExporter

    # From processed artifacts directory:
    report_md = MarkdownExporter.from_artifacts_dir("data/processed/MatALass")
    Path("portfolio_report.md").write_text(report_md, encoding="utf-8")

    # Or the HTML variant:
    report_html = MarkdownExporter.from_artifacts_dir(
        "data/processed/MatALass", output_format="html"
    )
    Path("portfolio_report.html").write_text(report_html, encoding="utf-8")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required artifact missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_optional(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _score_bar(score: float, width: int = 20) -> str:
    """ASCII progress bar for Markdown."""
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _decision_emoji(decision: str) -> str:
    return {
        "FEATURE_NOW": "🟢",
        "KEEP_AND_IMPROVE": "🟡",
        "MERGE_OR_REPOSITION": "🟠",
        "ARCHIVE_PUBLIC": "🔵",
        "MAKE_PRIVATE": "🔴",
    }.get(decision, "⚪")


def _decision_label(decision: str) -> str:
    return {
        "FEATURE_NOW": "Feature now",
        "KEEP_AND_IMPROVE": "Keep & improve",
        "MERGE_OR_REPOSITION": "Merge / reposition",
        "ARCHIVE_PUBLIC": "Archive public",
        "MAKE_PRIVATE": "Make private",
    }.get(decision, decision)


# ---------------------------------------------------------------------------
# Markdown builder
# ---------------------------------------------------------------------------


class _MarkdownBuilder:
    def __init__(self, owner: str) -> None:
        self._owner = owner
        self._lines: list[str] = []

    def h1(self, text: str) -> "_MarkdownBuilder":
        self._lines += [f"# {text}", ""]
        return self

    def h2(self, text: str) -> "_MarkdownBuilder":
        self._lines += [f"## {text}", ""]
        return self

    def h3(self, text: str) -> "_MarkdownBuilder":
        self._lines += [f"### {text}", ""]
        return self

    def p(self, text: str) -> "_MarkdownBuilder":
        self._lines += [text, ""]
        return self

    def hr(self) -> "_MarkdownBuilder":
        self._lines += ["---", ""]
        return self

    def bullet(self, text: str, indent: int = 0) -> "_MarkdownBuilder":
        self._lines.append("  " * indent + f"- {text}")
        return self

    def table(self, headers: list[str], rows: list[list[str]]) -> "_MarkdownBuilder":
        sep = ["-" * max(len(h), 3) for h in headers]
        self._lines.append("| " + " | ".join(headers) + " |")
        self._lines.append("| " + " | ".join(sep) + " |")
        for row in rows:
            self._lines.append("| " + " | ".join(str(c) for c in row) + " |")
        self._lines.append("")
        return self

    def build(self) -> str:
        return "\n".join(self._lines)


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------


def _section_header(md: _MarkdownBuilder, owner: str, site_payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    overview = site_payload.get("overview", {})
    md.h1(f"GitHub Portfolio Report · {owner}")
    md.p(f"*Generated {now}*")
    md.hr()
    summary = overview.get("manager_summary", "")
    if summary:
        md.h2("Executive summary")
        md.p(f"> {summary}")
    md.h2("Portfolio snapshot")
    md.table(
        ["Metric", "Value"],
        [
            ["Repositories analyzed", str(overview.get("total_repositories", 0))],
            ["Feature now", str(overview.get("featured_count", 0))],
            ["Keep & improve", str(overview.get("keep_visible_but_improve_count", 0))],
            ["Improvement backlog", str(overview.get("improvement_backlog_count", 0))],
            ["Archive candidates", str(overview.get("archive_candidates_count", 0))],
            ["Redundancy clusters", str(overview.get("overlap_clusters_count", 0))],
        ],
    )


def _section_featured(md: _MarkdownBuilder, ranking: list[dict[str, Any]]) -> None:
    featured = [r for r in ranking if r.get("portfolio_decision") == "FEATURE_NOW"]
    if not featured:
        return
    md.h2("🟢 Feature now")
    md.p("Repositories strong enough to showcase directly in your portfolio.")
    for repo in featured:
        score = repo.get("global_score", 0.0)
        bar = _score_bar(score)
        md.h3(f"{repo.get('repo_name')} · {score:.1f}/100")
        md.p(f"`{bar}` {score:.1f}%")
        desc = repo.get("description") or ""
        if desc:
            md.p(f"*{desc}*")
        lang = repo.get("primary_language") or "Unknown"
        stars = repo.get("stars", 0)
        url = repo.get("html_url", "")
        homepage = repo.get("homepage") or ""
        meta_parts = [f"**Language:** {lang}", f"**Stars:** {stars}"]
        if url:
            meta_parts.append(f"[GitHub]({url})")
        if homepage:
            meta_parts.append(f"[Demo]({homepage})")
        md.p("  ·  ".join(meta_parts))


def _section_backlog(md: _MarkdownBuilder, ranking: list[dict[str, Any]], review_index: dict[str, dict[str, Any]]) -> None:
    backlog = [
        r for r in ranking
        if r.get("portfolio_decision") in {"KEEP_AND_IMPROVE", "MERGE_OR_REPOSITION"}
    ]
    if not backlog:
        return
    md.h2("🟡 Improvement backlog")
    rows = []
    for repo in backlog:
        name = repo.get("repo_name", "")
        score = repo.get("global_score", 0.0)
        decision = repo.get("portfolio_decision", "")
        review = review_index.get(name, {})
        top_action = ""
        actions = review.get("priority_actions") or []
        if actions:
            top_action = str(actions[0].get("text", ""))[:60]
        rows.append([
            f"{_decision_emoji(decision)} {name}",
            f"{score:.1f}",
            _decision_label(decision),
            top_action,
        ])
    md.table(["Repository", "Score", "Decision", "Top priority action"], rows)


def _section_all_repos(md: _MarkdownBuilder, ranking: list[dict[str, Any]]) -> None:
    md.h2("📊 Full ranking")
    rows = []
    for repo in ranking:
        name = repo.get("repo_name", "")
        score = repo.get("global_score", 0.0)
        decision = repo.get("portfolio_decision", "")
        lang = repo.get("primary_language") or "—"
        stars = repo.get("stars", 0)
        confidence = repo.get("confidence", 0.0)
        redundancy = repo.get("redundancy_status", "UNIQUE")
        red_marker = "⚠" if redundancy == "OVERLAP_CANDIDATE" else ""
        rows.append([
            str(repo.get("rank", "")),
            f"{_decision_emoji(decision)} {name} {red_marker}",
            f"{score:.1f}",
            f"{confidence:.0%}",
            lang,
            str(stars),
            _decision_label(decision),
        ])
    md.table(
        ["#", "Repository", "Score", "Confidence", "Language", "⭐", "Decision"],
        rows,
    )


def _section_top_actions(md: _MarkdownBuilder, ranking_summary: dict[str, Any]) -> None:
    priority_repos = ranking_summary.get("highest_priority_improvements", [])
    if not priority_repos:
        return
    md.h2("🚀 Highest-priority improvements")
    md.p("Top repositories where targeted effort yields the best portfolio ROI.")
    for repo in priority_repos[:6]:
        name = repo.get("repo_name", "")
        score = repo.get("global_score", 0.0)
        actions_count = repo.get("priority_actions_count", 0)
        md.bullet(f"**{name}** — {score:.1f}/100 · {actions_count} priority action(s)")


def _section_redundancy(md: _MarkdownBuilder, redundancy: dict[str, Any]) -> None:
    clusters = redundancy.get("overlap_clusters", [])
    pairs = redundancy.get("overlap_pairs", [])
    if not clusters and not pairs:
        return
    md.h2("🔄 Redundancy analysis")
    if clusters:
        md.p(f"**{len(clusters)} overlap cluster(s) detected.** Consider merging or repositioning duplicate projects.")
        for cluster in clusters:
            cid = cluster.get("cluster_id", "")
            rep = cluster.get("representative_repo_full_name", "")
            members = cluster.get("repo_full_names", [])
            avg = cluster.get("average_overlap_score", 0.0)
            md.h3(f"{cid} · avg overlap {avg:.0%}")
            md.bullet(f"Representative: **{rep}**")
            for member in members:
                if member != rep:
                    md.bullet(f"Candidate: {member}", indent=1)
    if pairs:
        md.p(f"**{len(pairs)} overlap pair(s)** identified (threshold ≥ 0.58).")


def _section_footer(md: _MarkdownBuilder) -> None:
    md.hr()
    md.p("*Report generated by [GitHub Portfolio Auditor](https://github.com) — deterministic, policy-driven.*")


# ---------------------------------------------------------------------------
# HTML wrapper
# ---------------------------------------------------------------------------

_HTML_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 900px; margin: 40px auto; padding: 0 24px;
       color: #1a1a1a; line-height: 1.65; }
h1 { font-size: 2rem; border-bottom: 3px solid #2563eb; padding-bottom: 0.4rem; }
h2 { font-size: 1.4rem; margin-top: 2rem; color: #1e40af; }
h3 { font-size: 1.1rem; margin-top: 1.4rem; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
th { background: #f1f5f9; text-align: left; padding: 8px 12px;
     border: 1px solid #cbd5e1; font-weight: 600; }
td { padding: 6px 12px; border: 1px solid #e2e8f0; }
tr:nth-child(even) td { background: #f8fafc; }
blockquote { border-left: 4px solid #2563eb; margin: 0; padding: 0.6rem 1rem;
             background: #eff6ff; color: #1e3a8a; border-radius: 0 4px 4px 0; }
code { background: #f1f5f9; padding: 2px 5px; border-radius: 3px;
       font-family: 'SF Mono', 'Fira Mono', monospace; font-size: 0.85em; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 2rem 0; }
em { color: #475569; }
li { margin: 4px 0; }
"""


def _markdown_to_simple_html(md_text: str) -> str:
    """
    Minimal Markdown → HTML converter covering the subset we generate.
    Not a general-purpose converter — handles exactly what _MarkdownBuilder produces.
    """
    import re

    lines = md_text.split("\n")
    html_lines: list[str] = []
    in_table = False
    in_ul = False

    for line in lines:
        # Table row
        if line.startswith("|"):
            if not in_table:
                html_lines.append("<table>")
                in_table = True
                # first line is header
                cells = [c.strip() for c in line.strip("|").split("|")]
                html_lines.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr></thead><tbody>")
            elif re.match(r"^\|\s*-", line):
                continue  # separator row
            else:
                cells = [c.strip() for c in line.strip("|").split("|")]
                html_lines.append("<tr>" + "".join(f"<td>{_inline_md(c)}</td>" for c in cells) + "</tr>")
            continue
        elif in_table:
            html_lines.append("</tbody></table>")
            in_table = False

        # List item
        if re.match(r"^(\s*)- ", line):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            indent = len(line) - len(line.lstrip())
            content = line.lstrip("- ").strip()
            html_lines.append(f"<li style='margin-left:{indent * 8}px'>{_inline_md(content)}</li>")
            continue
        elif in_ul:
            html_lines.append("</ul>")
            in_ul = False

        # Headings
        if line.startswith("# "):
            html_lines.append(f"<h1>{_inline_md(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{_inline_md(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{_inline_md(line[4:])}</h3>")
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{_inline_md(line[2:])}</blockquote>")
        elif line.strip() == "---":
            html_lines.append("<hr>")
        elif line.strip() == "":
            html_lines.append("")
        else:
            html_lines.append(f"<p>{_inline_md(line)}</p>")

    if in_table:
        html_lines.append("</tbody></table>")
    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _inline_md(text: str) -> str:
    """Convert inline Markdown (bold, italic, code, links) to HTML."""
    import re

    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class MarkdownExporter:
    """
    Builds a portfolio audit report in Markdown or HTML format from processed
    artifacts.

    All methods are static — no instantiation needed.
    """

    @staticmethod
    def from_artifacts_dir(
        owner_dir: str | Path,
        *,
        output_format: str = "markdown",
    ) -> str:
        """
        Generate a report from the processed artifacts of an owner.

        Parameters
        ----------
        owner_dir:
            Path to ``data/processed/<owner>/``.
        output_format:
            ``"markdown"`` (default) or ``"html"``.

        Returns
        -------
        str
            The report as a Markdown or HTML string.
        """
        owner_dir = Path(owner_dir)
        owner = owner_dir.name

        ranking = _load(owner_dir / "ranking.json")
        ranking_summary = _load(owner_dir / "ranking_summary.json")
        site_payload = _load(owner_dir / "site_payload.json")
        redundancy = _load(owner_dir / "redundancy_analysis.json")
        reviews_raw = _load_optional(owner_dir / "repo_reviews.json") or []

        review_index: dict[str, dict[str, Any]] = {}
        for rev in reviews_raw:
            name = rev.get("repo_name") or ""
            if name:
                review_index[name] = rev

        md = _MarkdownBuilder(owner)
        _section_header(md, owner, site_payload)
        _section_featured(md, ranking)
        md.hr()
        _section_backlog(md, ranking, review_index)
        md.hr()
        _section_all_repos(md, ranking)
        md.hr()
        _section_top_actions(md, ranking_summary)
        md.hr()
        _section_redundancy(md, redundancy)
        _section_footer(md)

        report_md = md.build()

        if output_format == "html":
            return MarkdownExporter.to_html(report_md, owner=owner)
        return report_md

    @staticmethod
    def to_html(markdown_text: str, *, owner: str = "Portfolio") -> str:
        """Wrap a Markdown report in a minimal HTML page."""
        body = _markdown_to_simple_html(markdown_text)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{owner} · Portfolio Report · {now}</title>
<style>{_HTML_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""

    @staticmethod
    def export_to_file(
        owner_dir: str | Path,
        output_path: str | Path,
        *,
        output_format: str = "markdown",
    ) -> Path:
        """
        Generate a report and write it to a file.

        Returns the path of the written file.
        """
        report = MarkdownExporter.from_artifacts_dir(owner_dir, output_format=output_format)
        output_path = Path(output_path)
        output_path.write_text(report, encoding="utf-8")
        return output_path
