"""
exports/sqlite_exporter.py

SQLite export — not yet implemented.

Planned behaviour
-----------------
Export all audit artifacts (repos, scans, scores, reviews, ranking) into a
local SQLite database so consumers can run ad-hoc SQL queries against a full
audit run without depending on JSON files or the Streamlit dashboard.

Intended schema
---------------
  repos     — one row per RepoMetadata
  scans     — one row per RepoScanResult (foreign key: repo_name)
  scores    — one row per RepoScore (foreign key: repo_name)
  reviews   — one row per RepoReview (foreign key: repo_name)
  ranking   — one row per RankedRepo (foreign key: repo_name)

Until this is implemented, importing from this module raises NotImplementedError.
Track progress at: docs/roadmap.md — Phase 4.
"""

from __future__ import annotations


class SqliteExporter:
    """Export audit artifacts to a local SQLite database."""

    def export(self) -> None:  # pragma: no cover
        raise NotImplementedError(
            "SqliteExporter is not yet implemented. "
            "See exports/sqlite_exporter.py for the planned schema."
        )