"""
scoring/calibration.py

Empirical weight calibration for the scoring policy.

Problem
-------
The weights in v1.yaml are arbitrary (e.g. architecture=20, documentation=20).
There is no evidence that they reflect how a recruiter actually judges a portfolio.

This module provides two things:

1. ``WeightCalibrator`` — fits OLS regression to map score breakdowns → a
   reference score (human rating or proxy like stars+forks), then suggests
   updated weights in a format ready to paste into the policy YAML.

2. ``calibrate_from_processed_artifacts`` — convenience entry point that reads
   the existing ``repo_scores.json`` + ``repos_metadata.json`` artifacts and
   runs the calibration, producing a suggested policy update.

Design choices
--------------
- Pure stdlib + existing project deps (no numpy/scipy required).
- OLS via normal equations implemented with basic arithmetic, so the calibration
  runs without any additional dependencies.
- Uses a proxy target by default (engagement signal: log(stars+1) + log(forks+1))
  since human-annotated scores are not available yet. Once you collect real human
  ratings, pass them as ``reference_scores``.
- Weights are clamped to [min_weight, max_weight] and re-normalized to sum to
  100.0 so they remain a valid policy.
- The calibration is intentionally lightweight: it is a diagnostic tool, not an
  auto-updater. It prints a suggested YAML block; you decide whether to apply it.

Usage
-----
    from portfolio_auditor.scoring.calibration import calibrate_from_processed_artifacts
    result = calibrate_from_processed_artifacts("data/processed/MatALass")
    print(result.suggested_yaml_block)

Or from the CLI (if wired up):
    python -m portfolio_auditor.scoring.calibration --owner MatALass
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BREAKDOWN_CATEGORIES = [
    "architecture_structure",
    "documentation_delivery",
    "testing_reliability",
    "technical_depth",
    "portfolio_relevance",
    "maintainability_cleanliness",
]

POLICY_WEIGHT_NAMES = {
    "architecture_structure": "architecture",
    "documentation_delivery": "documentation",
    "testing_reliability": "testing",
    "technical_depth": "technical_depth",
    "portfolio_relevance": "portfolio_relevance",
    "maintainability_cleanliness": "maintainability",
}

# Minimum and maximum weight for any single category (to avoid degenerate solutions)
_MIN_WEIGHT = 5.0
_MAX_WEIGHT = 35.0
_TOTAL_WEIGHT = 100.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationSample:
    """One repo's breakdown vector and its reference (target) score."""

    repo_full_name: str
    breakdown: dict[str, float]  # category → raw sub-score (pre-weight)
    reference_score: float  # target to regress against


@dataclass(frozen=True)
class CalibrationResult:
    """Output of a calibration run."""

    n_samples: int
    fitted_weights: dict[str, float]  # category → suggested weight (sum ≈ 100)
    current_weights: dict[str, float]  # policy weight names → current values
    r_squared: float
    rmse: float
    suggested_yaml_block: str
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# OLS via normal equations (pure Python, no numpy)
# ---------------------------------------------------------------------------


def _dot(u: list[float], v: list[float]) -> float:
    return sum(a * b for a, b in zip(u, v, strict=True))


def _mat_vec(matrix: list[list[float]], vec: list[float]) -> list[float]:
    return [_dot(row, vec) for row in matrix]


def _mat_mat(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    cols_b = len(b[0])
    bt = [[b[r][c] for r in range(len(b))] for c in range(cols_b)]
    return [[_dot(row_a, col_b) for col_b in bt] for row_a in a]


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    rows, cols = len(matrix), len(matrix[0])
    return [[matrix[r][c] for r in range(rows)] for c in range(cols)]


def _inverse_2x2(m: list[list[float]]) -> list[list[float]] | None:
    """Only used as a safety fallback for tiny systems."""
    if len(m) != 2:
        return None
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    if abs(det) < 1e-12:
        return None
    inv_det = 1.0 / det
    return [
        [m[1][1] * inv_det, -m[0][1] * inv_det],
        [-m[1][0] * inv_det, m[0][0] * inv_det],
    ]


def _gauss_jordan(a: list[list[float]], b: list[float]) -> list[float] | None:
    """
    Solve Ax = b via Gauss-Jordan elimination with partial pivoting.
    Returns None if the system is singular.
    """
    n = len(b)
    # Augmented matrix [A | b]
    aug = [row[:] + [bi] for row, bi in zip(a, b, strict=True)]

    for col in range(n):
        # Find pivot
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-12:
            return None
        aug[col], aug[pivot_row] = aug[pivot_row], aug[col]

        pivot = aug[col][col]
        aug[col] = [v / pivot for v in aug[col]]

        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            aug[row] = [aug[row][j] - factor * aug[col][j] for j in range(n + 1)]

    return [aug[row][n] for row in range(n)]


def _ols_fit(x_matrix: list[list[float]], y: list[float]) -> list[float] | None:
    """
    OLS via normal equations: β = (XᵀX)⁻¹Xᵀy
    Returns None if the system cannot be solved.
    """
    xt = _transpose(x_matrix)
    xtx = _mat_mat(xt, x_matrix)
    xty = _mat_vec(xt, y)
    return _gauss_jordan(xtx, xty)


# ---------------------------------------------------------------------------
# Proxy target builder
# ---------------------------------------------------------------------------


def _proxy_target(stars: int, forks: int, global_score: float) -> float:
    """
    Engagement-based proxy target score in [0, 100].

    Combines log-transformed engagement (stars + forks) with the existing
    global score. The engagement component is a weak signal — it is used
    only when no human-annotated reference score is available.

    Logic: we assume that engagement (stars/forks) is a noisy proxy for
    quality, but the existing global score already captures most of the
    signal. So we blend 70% existing score + 30% engagement signal.
    """
    engagement = math.log1p(stars) + math.log1p(forks)
    # Normalize engagement to roughly [0, 100] assuming max ≈ log(1001)*2 ≈ 14
    engagement_normalized = min(100.0, engagement / 14.0 * 100.0)
    return round(0.70 * global_score + 0.30 * engagement_normalized, 2)


# ---------------------------------------------------------------------------
# Main calibrator
# ---------------------------------------------------------------------------


class WeightCalibrator:
    """
    Fits a linear model to map raw score components → reference scores,
    then converts the fitted coefficients to policy-compatible weights.

    Parameters
    ----------
    min_weight, max_weight:
        Bounds applied after fitting to keep weights sane.
    total_weight:
        Target sum for the output weights (default 100.0 to match the policy).
    """

    def __init__(
        self,
        min_weight: float = _MIN_WEIGHT,
        max_weight: float = _MAX_WEIGHT,
        total_weight: float = _TOTAL_WEIGHT,
    ) -> None:
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.total_weight = total_weight

    def fit(
        self,
        samples: list[CalibrationSample],
        current_weights: dict[str, float],
    ) -> CalibrationResult:
        notes: list[str] = []

        if len(samples) < len(BREAKDOWN_CATEGORIES) + 1:
            notes.append(
                f"Only {len(samples)} samples — OLS may overfit. "
                "Collect more repos (at least 10–20) for reliable calibration."
            )

        # Build design matrix: each row = [raw_sub_score / weight → ratio in [0,1]] per category
        # We regress on the *ratio* (raw / max_possible), not the weighted value.
        # This decouples the current weights from the regression target.
        x_matrix: list[list[float]] = []
        y_vec: list[float] = []
        max_per_category = {
            "architecture_structure": 20.0,
            "documentation_delivery": 20.0,
            "testing_reliability": 15.0,
            "technical_depth": 15.0,
            "portfolio_relevance": 20.0,
            "maintainability_cleanliness": 10.0,
        }

        for sample in samples:
            row = []
            for cat in BREAKDOWN_CATEGORIES:
                weighted_score = sample.breakdown.get(cat, 0.0)
                current_w = current_weights.get(POLICY_WEIGHT_NAMES[cat], 20.0)
                # Recover the ratio: weighted_score / current_weight = ratio
                ratio = weighted_score / current_w if current_w > 0 else 0.0
                row.append(ratio)
            x_matrix.append(row)
            y_vec.append(sample.reference_score)

        coefficients = _ols_fit(x_matrix, y_vec)

        if coefficients is None:
            notes.append("OLS failed (singular matrix) — using equal weights as fallback.")
            equal_w = self.total_weight / len(BREAKDOWN_CATEGORIES)
            fitted = {cat: equal_w for cat in BREAKDOWN_CATEGORIES}
        else:
            # Raw coefficients represent the contribution per unit ratio — treat as weights
            raw = {
                cat: max(0.0, coeff)
                for cat, coeff in zip(BREAKDOWN_CATEGORIES, coefficients, strict=True)
            }
            fitted = self._normalize_and_clamp(raw)

        # Compute R² and RMSE on the fitted weights
        fitted_scores = self._predict(x_matrix, fitted, max_per_category)
        r_squared = self._r_squared(y_vec, fitted_scores)
        rmse = self._rmse(y_vec, fitted_scores)

        if r_squared < 0.3:
            notes.append(
                f"R²={r_squared:.3f} is low — the engagement proxy may be a weak signal. "
                "Consider annotating repos manually and re-running calibration."
            )

        yaml_block = self._build_yaml_block(fitted)

        return CalibrationResult(
            n_samples=len(samples),
            fitted_weights=fitted,
            current_weights=current_weights,
            r_squared=r_squared,
            rmse=rmse,
            suggested_yaml_block=yaml_block,
            notes=notes,
        )

    def _normalize_and_clamp(self, raw: dict[str, float]) -> dict[str, float]:
        """Normalize raw weights to ``total_weight`` while respecting hard bounds."""
        if not raw:
            return {}

        keys = list(raw.keys())
        n = len(keys)
        min_total = self.min_weight * n
        max_total = self.max_weight * n
        if self.total_weight < min_total - 1e-9 or self.total_weight > max_total + 1e-9:
            raise ValueError(
                "total_weight is incompatible with the configured min/max bounds "
                f"for {n} categories: {self.total_weight=} not in [{min_total}, {max_total}]"
            )

        positive_raw = {k: max(0.0, float(v)) for k, v in raw.items()}
        base = {k: self.min_weight for k in keys}
        remaining_budget = self.total_weight - self.min_weight * n

        if remaining_budget <= 1e-12:
            return {k: round(v, 2) for k, v in base.items()}

        capacities = {k: self.max_weight - self.min_weight for k in keys}
        active = set(keys)
        extra = {k: 0.0 for k in keys}

        while active and remaining_budget > 1e-12:
            active_total = sum(positive_raw[k] for k in active)
            if active_total <= 1e-12:
                equal_share = remaining_budget / len(active)
                for k in list(active):
                    give = min(capacities[k] - extra[k], equal_share)
                    extra[k] += give
                break

            saturated: set[str] = set()
            allocated = 0.0
            for k in list(active):
                target = remaining_budget * (positive_raw[k] / active_total)
                give = min(capacities[k] - extra[k], target)
                extra[k] += give
                allocated += give
                if capacities[k] - extra[k] <= 1e-12:
                    saturated.add(k)

            if allocated <= 1e-12:
                remaining_capacity = [k for k in active if capacities[k] - extra[k] > 1e-12]
                if not remaining_capacity:
                    break
                equal_share = remaining_budget / len(remaining_capacity)
                for k in remaining_capacity:
                    give = min(capacities[k] - extra[k], equal_share)
                    extra[k] += give
                break

            remaining_budget -= allocated
            active -= saturated
            if not saturated and remaining_budget > 1e-12:
                break

        normalized = {k: base[k] + extra[k] for k in keys}

        diff = round(self.total_weight - sum(normalized.values()), 2)
        if diff != 0:
            adjustable = [
                k
                for k in reversed(keys)
                if self.min_weight - 1e-9 <= normalized[k] + diff <= self.max_weight + 1e-9
            ]
            if adjustable:
                normalized[adjustable[0]] += diff

        return {k: round(v, 2) for k, v in normalized.items()}

    @staticmethod
    def _predict(
        x_matrix: list[list[float]],
        weights: dict[str, float],
        max_per_category: dict[str, float],
    ) -> list[float]:
        w_vec = [weights[cat] for cat in BREAKDOWN_CATEGORIES]
        predictions = []
        for row in x_matrix:
            score = sum(ratio * w for ratio, w in zip(row, w_vec, strict=True))
            predictions.append(min(100.0, max(0.0, score)))
        return predictions

    @staticmethod
    def _r_squared(actual: list[float], predicted: list[float]) -> float:
        mean_y = sum(actual) / len(actual)
        ss_tot = sum((y - mean_y) ** 2 for y in actual)
        ss_res = sum((y - yhat) ** 2 for y, yhat in zip(actual, predicted, strict=True))
        if ss_tot < 1e-12:
            return 1.0
        return round(1.0 - ss_res / ss_tot, 4)

    @staticmethod
    def _rmse(actual: list[float], predicted: list[float]) -> float:
        mse = sum((y - yhat) ** 2 for y, yhat in zip(actual, predicted, strict=True)) / len(actual)
        return round(math.sqrt(mse), 4)

    @staticmethod
    def _build_yaml_block(weights: dict[str, float]) -> str:
        lines = ["# Suggested weights from calibration — review before applying", "weights:"]
        for cat, policy_name in POLICY_WEIGHT_NAMES.items():
            lines.append(f"  {policy_name}: {weights[cat]}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _build_samples(
    scores: list[dict[str, Any]],
    metadata: list[dict[str, Any]],
    reference_scores: dict[str, float] | None = None,
) -> list[CalibrationSample]:
    meta_index = {item["full_name"]: item for item in metadata if "full_name" in item}

    samples: list[CalibrationSample] = []
    for score_entry in scores:
        full_name = score_entry.get("repo_full_name", "")
        breakdown = score_entry.get("breakdown") or {}
        global_score = float(score_entry.get("global_score", 0.0))

        if reference_scores and full_name in reference_scores:
            ref = reference_scores[full_name]
        else:
            meta = meta_index.get(full_name, {})
            engagement = meta.get("engagement") or {}
            stars = int(engagement.get("stargazers_count", 0))
            forks = int(engagement.get("forks_count", 0))
            ref = _proxy_target(stars, forks, global_score)

        samples.append(
            CalibrationSample(
                repo_full_name=full_name,
                breakdown={k: float(v) for k, v in breakdown.items()},
                reference_score=ref,
            )
        )
    return samples


def calibrate_from_processed_artifacts(
    owner_dir: str | Path,
    *,
    reference_scores: dict[str, float] | None = None,
    current_weights: dict[str, float] | None = None,
) -> CalibrationResult:
    """
    Run calibration from the processed artifacts of an owner.

    Parameters
    ----------
    owner_dir:
        Path to ``data/processed/<owner>/``.
    reference_scores:
        Optional mapping of ``repo_full_name → human_rating`` (0–100).
        If omitted, an engagement-based proxy is used.
    current_weights:
        Current policy weight values (policy_name → float).
        If omitted, the v1 defaults are used.

    Returns
    -------
    CalibrationResult
        Includes suggested YAML block and diagnostic stats.
    """
    owner_dir = Path(owner_dir)
    scores_path = owner_dir / "repo_scores.json"
    meta_path = owner_dir / "repos_metadata.json"

    if not scores_path.exists():
        raise FileNotFoundError(f"repo_scores.json not found in {owner_dir}")
    if not meta_path.exists():
        raise FileNotFoundError(f"repos_metadata.json not found in {owner_dir}")

    scores = _load_json(scores_path)
    metadata = _load_json(meta_path)

    if current_weights is None:
        current_weights = {
            "architecture": 20.0,
            "documentation": 20.0,
            "testing": 15.0,
            "technical_depth": 15.0,
            "portfolio_relevance": 20.0,
            "maintainability": 10.0,
        }

    samples = _build_samples(scores, metadata, reference_scores)
    calibrator = WeightCalibrator()
    result = calibrator.fit(samples, current_weights)

    logger.info(
        "Calibration complete: %d samples, R²=%.3f, RMSE=%.2f",
        result.n_samples,
        result.r_squared,
        result.rmse,
    )
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Calibrate scoring weights from processed artifacts."
    )
    parser.add_argument("--owner", required=True, help="GitHub owner whose artifacts to use")
    parser.add_argument(
        "--data-dir", default="data/processed", help="Base processed data directory"
    )
    args = parser.parse_args()

    owner_dir = Path(args.data_dir) / args.owner
    result = calibrate_from_processed_artifacts(owner_dir)

    print(f"\nCalibration result — {result.n_samples} repos")
    print(f"R²: {result.r_squared:.4f}  |  RMSE: {result.rmse:.2f}")

    if result.notes:
        print("\nNotes:")
        for note in result.notes:
            print(f"  • {note}")

    print(f"\nCurrent weights: {result.current_weights}")
    print(f"Fitted weights:  {result.fitted_weights}")
    print(f"\n{result.suggested_yaml_block}")
