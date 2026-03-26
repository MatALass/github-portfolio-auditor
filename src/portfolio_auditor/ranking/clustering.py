from __future__ import annotations

from collections import defaultdict


def cluster_by_decision(rows: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for row in rows:
        groups[row.get("portfolio_decision", "UNKNOWN")].append(row)
    return dict(groups)
