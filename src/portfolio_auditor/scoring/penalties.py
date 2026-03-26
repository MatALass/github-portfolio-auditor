from __future__ import annotations

from portfolio_auditor.models.repo_score import Penalty
from portfolio_auditor.models.repo_scan import RepoScan


def compute_penalties(scan: RepoScan) -> list[Penalty]:
    penalties: list[Penalty] = []
    for issue in scan.all_issues:
        if issue.code == "MISSING_README":
            penalties.append(Penalty(code=issue.code, points=-10, reason=issue.message))
        elif issue.code == "NO_TESTS_DETECTED":
            penalties.append(Penalty(code=issue.code, points=-8, reason=issue.message))
        elif issue.code == "NO_CI_WORKFLOW":
            penalties.append(Penalty(code=issue.code, points=-4, reason=issue.message))
        elif issue.code == "COMMITTED_ARTIFACTS":
            penalties.append(Penalty(code=issue.code, points=-3, reason=issue.message))
        elif issue.code == "NO_DEPENDENCY_MANIFEST":
            penalties.append(Penalty(code=issue.code, points=-8, reason=issue.message))
    return penalties
