from __future__ import annotations

from enum import Enum


class PortfolioDecision(str, Enum):
    """
    Final recommended status for a repository in the portfolio strategy.
    """

    FEATURE_NOW = "FEATURE_NOW"
    KEEP_AND_IMPROVE = "KEEP_AND_IMPROVE"
    MERGE_OR_REPOSITION = "MERGE_OR_REPOSITION"
    ARCHIVE_PUBLIC = "ARCHIVE_PUBLIC"
    MAKE_PRIVATE = "MAKE_PRIVATE"