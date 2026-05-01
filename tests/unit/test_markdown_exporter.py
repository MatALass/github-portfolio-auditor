"""
tests/unit/test_markdown_exporter.py

Unit tests for exports/markdown_exporter.py.

Tests cover:
- _score_bar output format
- _decision_emoji and _decision_label mappings
- _MarkdownBuilder produces valid Markdown
- _inline_md converts bold/italic/code/links
- _markdown_to_simple_html produces HTML tags
- MarkdownExporter.from_artifacts_dir with a fake artifacts directory
- MarkdownExporter.to_html wraps content correctly
- MarkdownExporter.export_to_file writes the file
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from portfolio_auditor.exports.markdown_exporter import (
    MarkdownExporter,
    _decision_emoji,
    _decision_label,
    _inline_md,
    _markdown_to_simple_html,
    _MarkdownBuilder,
    _score_bar,
)

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestScoreBar:
    def test_full_score_all_filled(self) -> None:
        bar = _score_bar(100.0, width=10)
        assert bar == "█" * 10

    def test_zero_score_all_empty(self) -> None:
        bar = _score_bar(0.0, width=10)
        assert bar == "░" * 10

    def test_half_score(self) -> None:
        bar = _score_bar(50.0, width=10)
        assert bar.count("█") == 5
        assert bar.count("░") == 5

    def test_length_matches_width(self) -> None:
        for score in [0.0, 25.0, 75.0, 100.0]:
            assert len(_score_bar(score, width=20)) == 20


class TestDecisionHelpers:
    def test_feature_now_emoji(self) -> None:
        assert _decision_emoji("FEATURE_NOW") == "🟢"

    def test_make_private_emoji(self) -> None:
        assert _decision_emoji("MAKE_PRIVATE") == "🔴"

    def test_unknown_decision_returns_default_emoji(self) -> None:
        assert _decision_emoji("TOTALLY_UNKNOWN") == "⚪"

    def test_feature_now_label(self) -> None:
        assert _decision_label("FEATURE_NOW") == "Feature now"

    def test_unknown_label_passes_through(self) -> None:
        assert _decision_label("CUSTOM") == "CUSTOM"


# ---------------------------------------------------------------------------
# _MarkdownBuilder
# ---------------------------------------------------------------------------


class TestMarkdownBuilder:
    def test_h1_present_in_output(self) -> None:
        md = _MarkdownBuilder("owner")
        md.h1("My Title")
        assert "# My Title" in md.build()

    def test_h2_present(self) -> None:
        md = _MarkdownBuilder("owner")
        md.h2("Section")
        assert "## Section" in md.build()

    def test_table_contains_headers(self) -> None:
        md = _MarkdownBuilder("owner")
        md.table(["Name", "Score"], [["repo-a", "85.0"], ["repo-b", "70.0"]])
        output = md.build()
        assert "| Name | Score |" in output
        assert "repo-a" in output
        assert "repo-b" in output

    def test_bullet_indent(self) -> None:
        md = _MarkdownBuilder("owner")
        md.bullet("top level")
        md.bullet("nested", indent=1)
        output = md.build()
        assert "- top level" in output
        assert "  - nested" in output

    def test_hr_in_output(self) -> None:
        md = _MarkdownBuilder("owner")
        md.hr()
        assert "---" in md.build()

    def test_chaining_returns_self(self) -> None:
        md = _MarkdownBuilder("owner")
        result = md.h1("x").h2("y").p("z").hr()
        assert result is md


# ---------------------------------------------------------------------------
# _inline_md
# ---------------------------------------------------------------------------


class TestInlineMd:
    def test_bold(self) -> None:
        assert _inline_md("**hello**") == "<strong>hello</strong>"

    def test_italic(self) -> None:
        assert _inline_md("*world*") == "<em>world</em>"

    def test_code(self) -> None:
        assert _inline_md("`foo`") == "<code>foo</code>"

    def test_link(self) -> None:
        result = _inline_md("[GitHub](https://github.com)")
        assert 'href="https://github.com"' in result
        assert "GitHub" in result

    def test_plain_text_unchanged(self) -> None:
        assert _inline_md("hello world") == "hello world"


# ---------------------------------------------------------------------------
# _markdown_to_simple_html
# ---------------------------------------------------------------------------


class TestMarkdownToSimpleHtml:
    def test_h1_converted(self) -> None:
        assert "<h1>" in _markdown_to_simple_html("# Hello")

    def test_h2_converted(self) -> None:
        assert "<h2>" in _markdown_to_simple_html("## Section")

    def test_table_converted(self) -> None:
        md = "| A | B |\n| - | - |\n| x | y |"
        html = _markdown_to_simple_html(md)
        assert "<table>" in html
        assert "<th>" in html
        assert "<td>" in html

    def test_blockquote_converted(self) -> None:
        assert "<blockquote>" in _markdown_to_simple_html("> note")

    def test_hr_converted(self) -> None:
        assert "<hr>" in _markdown_to_simple_html("---")

    def test_list_items_converted(self) -> None:
        html = _markdown_to_simple_html("- item one\n- item two")
        assert "<ul>" in html
        assert "<li>" in html


# ---------------------------------------------------------------------------
# MarkdownExporter — from_artifacts_dir
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _fake_artifacts(tmp_path: Path) -> Path:
    """Create a minimal set of fake artifacts that the exporter can read."""
    owner_dir = tmp_path / "TestOwner"

    ranking = [
        {
            "rank": 1,
            "repo_name": "great-project",
            "repo_full_name": "TestOwner/great-project",
            "global_score": 88.0,
            "score_label": "excellent",
            "confidence": 0.95,
            "portfolio_decision": "FEATURE_NOW",
            "primary_language": "Python",
            "description": "A great project",
            "owner_login": "TestOwner",
            "html_url": "https://github.com/TestOwner/great-project",
            "homepage": None,
            "strengths_count": 3,
            "weaknesses_count": 1,
            "blockers_count": 0,
            "priority_actions_count": 1,
            "stars": 12,
            "forks": 2,
            "overlap_cluster_id": None,
            "overlap_candidate_count": 0,
            "strongest_overlap_score": 0.0,
            "redundancy_status": "UNIQUE",
            "redundancy_reason": None,
            "representative_repo_full_name": None,
        },
        {
            "rank": 2,
            "repo_name": "work-in-progress",
            "repo_full_name": "TestOwner/work-in-progress",
            "global_score": 55.0,
            "score_label": "fair",
            "confidence": 0.7,
            "portfolio_decision": "KEEP_AND_IMPROVE",
            "primary_language": "TypeScript",
            "description": "Still in progress",
            "owner_login": "TestOwner",
            "html_url": "https://github.com/TestOwner/work-in-progress",
            "homepage": None,
            "strengths_count": 1,
            "weaknesses_count": 3,
            "blockers_count": 1,
            "priority_actions_count": 3,
            "stars": 0,
            "forks": 0,
            "overlap_cluster_id": None,
            "overlap_candidate_count": 0,
            "strongest_overlap_score": 0.0,
            "redundancy_status": "UNIQUE",
            "redundancy_reason": None,
            "representative_repo_full_name": None,
        },
    ]

    ranking_summary = {
        "ranked_repos": ranking,
        "highest_priority_improvements": [ranking[1]],
        "redundancy_analysis": {"overlap_clusters": [], "overlap_pairs": []},
        "feature_now": [ranking[0]],
        "keep_and_improve": [ranking[1]],
        "merge_or_reposition": [],
        "archive_public": [],
        "make_private": [],
        "top_repos": ranking,
        "worst_repos": [ranking[1]],
    }

    site_payload = {
        "generated_for_owner": "TestOwner",
        "overview": {
            "total_repositories": 2,
            "featured_count": 1,
            "keep_visible_but_improve_count": 1,
            "improvement_backlog_count": 1,
            "archive_candidates_count": 0,
            "private_candidates_count": 0,
            "redundancy_candidates_count": 0,
            "overlap_clusters_count": 0,
            "manager_summary": "Portfolio is on track. One repo ready to feature.",
            "decision_buckets": [],
        },
        "repositories": [],
    }

    redundancy = {"overlap_clusters": [], "overlap_pairs": [], "repo_statuses": {}}

    reviews = [
        {
            "repo_name": "work-in-progress",
            "repo_full_name": "TestOwner/work-in-progress",
            "priority_actions": [{"text": "Write a complete README.", "priority": "high"}],
            "quick_wins": [],
            "blockers": [],
            "strengths": [],
            "weaknesses": [],
        }
    ]

    _write_json(owner_dir / "ranking.json", ranking)
    _write_json(owner_dir / "ranking_summary.json", ranking_summary)
    _write_json(owner_dir / "site_payload.json", site_payload)
    _write_json(owner_dir / "redundancy_analysis.json", redundancy)
    _write_json(owner_dir / "repo_reviews.json", reviews)

    return owner_dir


class TestMarkdownExporterFromArtifacts:
    def test_returns_non_empty_markdown(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir)
        assert len(result) > 100

    def test_markdown_contains_owner_name(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir)
        assert "TestOwner" in result

    def test_markdown_contains_featured_repo(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir)
        assert "great-project" in result

    def test_markdown_contains_score(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir)
        assert "88" in result

    def test_markdown_contains_table(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir)
        assert "|" in result  # table syntax

    def test_html_format_wraps_in_doctype(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir, output_format="html")
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "</html>" in result

    def test_html_contains_css(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir, output_format="html")
        assert "<style>" in result

    def test_html_contains_repo_name(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        result = MarkdownExporter.from_artifacts_dir(owner_dir, output_format="html")
        assert "great-project" in result

    def test_missing_ranking_raises(self, tmp_path: Path) -> None:
        owner_dir = tmp_path / "Empty"
        owner_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            MarkdownExporter.from_artifacts_dir(owner_dir)

    def test_export_to_file_markdown(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        output_path = tmp_path / "report.md"
        result_path = MarkdownExporter.export_to_file(owner_dir, output_path)
        assert result_path.exists()
        content = result_path.read_text(encoding="utf-8")
        assert "TestOwner" in content

    def test_export_to_file_html(self, tmp_path: Path) -> None:
        owner_dir = _fake_artifacts(tmp_path)
        output_path = tmp_path / "report.html"
        MarkdownExporter.export_to_file(owner_dir, output_path, output_format="html")
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content


class TestMarkdownExporterToHtml:
    def test_wraps_body(self) -> None:
        html = MarkdownExporter.to_html("# Hello\n\nWorld", owner="Test")
        assert "<body>" in html
        assert "Hello" in html

    def test_title_contains_owner(self) -> None:
        html = MarkdownExporter.to_html("# x", owner="MyOwner")
        assert "MyOwner" in html
