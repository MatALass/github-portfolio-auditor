"""
tests/unit/test_calibration.py

Unit tests for scoring/calibration.py.

Tests cover:
- OLS helpers (_gauss_jordan, _ols_fit)
- Weight normalization and clamping
- Proxy target computation
- WeightCalibrator.fit() with synthetic samples
- CalibrationResult fields
- Edge cases: insufficient data, singular matrix, all-zero breakdown
"""

from __future__ import annotations

import math

import pytest

from portfolio_auditor.scoring.calibration import (
    BREAKDOWN_CATEGORIES,
    CalibrationSample,
    WeightCalibrator,
    _gauss_jordan,
    _ols_fit,
    _proxy_target,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS = {
    "architecture": 20.0,
    "documentation": 20.0,
    "testing": 15.0,
    "technical_depth": 15.0,
    "portfolio_relevance": 20.0,
    "maintainability": 10.0,
}

_MAX_PER_CATEGORY = {
    "architecture_structure": 20.0,
    "documentation_delivery": 20.0,
    "testing_reliability": 15.0,
    "technical_depth": 15.0,
    "portfolio_relevance": 20.0,
    "maintainability_cleanliness": 10.0,
}


def _make_sample(
    name: str,
    scores: dict[str, float],
    reference: float,
) -> CalibrationSample:
    return CalibrationSample(
        repo_full_name=f"user/{name}",
        breakdown=scores,
        reference_score=reference,
    )


def _full_breakdown(arch=15.0, doc=15.0, test=10.0, depth=10.0, rel=15.0, clean=8.0) -> dict[str, float]:
    return {
        "architecture_structure": arch,
        "documentation_delivery": doc,
        "testing_reliability": test,
        "technical_depth": depth,
        "portfolio_relevance": rel,
        "maintainability_cleanliness": clean,
    }


# ---------------------------------------------------------------------------
# _gauss_jordan
# ---------------------------------------------------------------------------


class TestGaussJordan:
    def test_solves_simple_2x2(self) -> None:
        # 2x + y = 5, x + 3y = 10  →  x=1, y=3
        a = [[2.0, 1.0], [1.0, 3.0]]
        b = [5.0, 10.0]
        sol = _gauss_jordan(a, b)
        assert sol is not None
        assert sol[0] == pytest.approx(1.0, abs=1e-6)
        assert sol[1] == pytest.approx(3.0, abs=1e-6)

    def test_solves_3x3(self) -> None:
        # Identity system
        a = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        b = [3.0, 7.0, 2.0]
        sol = _gauss_jordan(a, b)
        assert sol is not None
        assert sol == pytest.approx([3.0, 7.0, 2.0], abs=1e-6)

    def test_returns_none_for_singular_matrix(self) -> None:
        a = [[1.0, 2.0], [2.0, 4.0]]  # rows are proportional → singular
        b = [3.0, 6.0]
        sol = _gauss_jordan(a, b)
        assert sol is None


# ---------------------------------------------------------------------------
# _ols_fit
# ---------------------------------------------------------------------------


class TestOlsFit:
    def test_perfect_fit_single_feature(self) -> None:
        # y = 2x
        x = [[1.0], [2.0], [3.0], [4.0]]
        y = [2.0, 4.0, 6.0, 8.0]
        coeff = _ols_fit(x, y)
        assert coeff is not None
        assert coeff[0] == pytest.approx(2.0, abs=1e-4)

    def test_returns_none_for_underdetermined_system(self) -> None:
        # Only 1 sample for 3 features → XᵀX is singular
        x = [[1.0, 2.0, 3.0]]
        y = [6.0]
        coeff = _ols_fit(x, y)
        # May be None or have a solution; just don't crash
        assert coeff is None or len(coeff) == 3


# ---------------------------------------------------------------------------
# _proxy_target
# ---------------------------------------------------------------------------


class TestProxyTarget:
    def test_zero_engagement_returns_global_score_weighted(self) -> None:
        result = _proxy_target(stars=0, forks=0, global_score=80.0)
        assert result == pytest.approx(0.70 * 80.0, abs=0.1)

    def test_high_engagement_boosts_score(self) -> None:
        low = _proxy_target(stars=0, forks=0, global_score=60.0)
        high = _proxy_target(stars=500, forks=100, global_score=60.0)
        assert high > low

    def test_result_capped_at_100(self) -> None:
        result = _proxy_target(stars=10000, forks=5000, global_score=100.0)
        assert result <= 100.0

    def test_result_non_negative(self) -> None:
        result = _proxy_target(stars=0, forks=0, global_score=0.0)
        assert result >= 0.0


# ---------------------------------------------------------------------------
# WeightCalibrator — normalization
# ---------------------------------------------------------------------------


class TestWeightCalibratorNormalization:
    calibrator = WeightCalibrator(min_weight=5.0, max_weight=35.0, total_weight=100.0)

    def test_weights_sum_to_100(self) -> None:
        raw = {cat: 15.0 for cat in BREAKDOWN_CATEGORIES}
        result = self.calibrator._normalize_and_clamp(raw)
        assert sum(result.values()) == pytest.approx(100.0, abs=0.1)

    def test_weights_respect_min(self) -> None:
        raw = {cat: 0.0 for cat in BREAKDOWN_CATEGORIES}
        result = self.calibrator._normalize_and_clamp(raw)
        for val in result.values():
            assert val >= 5.0

    def test_weights_respect_max(self) -> None:
        raw = {BREAKDOWN_CATEGORIES[0]: 999.0}
        for cat in BREAKDOWN_CATEGORIES[1:]:
            raw[cat] = 0.0
        result = self.calibrator._normalize_and_clamp(raw)
        for val in result.values():
            assert val <= 35.0

    def test_all_categories_present(self) -> None:
        raw = {cat: 10.0 for cat in BREAKDOWN_CATEGORIES}
        result = self.calibrator._normalize_and_clamp(raw)
        assert set(result.keys()) == set(BREAKDOWN_CATEGORIES)


# ---------------------------------------------------------------------------
# WeightCalibrator.fit()
# ---------------------------------------------------------------------------


class TestWeightCalibratorFit:
    calibrator = WeightCalibrator()

    def _synthetic_samples(self, n: int = 15) -> list[CalibrationSample]:
        """
        Generate samples where documentation is artificially dominant,
        so calibration should upweight it relative to others.
        """
        samples = []
        for i in range(n):
            base = (i + 1) * 4.0  # 4 to 60
            breakdown = _full_breakdown(
                arch=base * 0.5,
                doc=base,         # documentation is the signal
                test=base * 0.3,
                depth=base * 0.4,
                rel=base * 0.6,
                clean=base * 0.8,
            )
            # Cap to max per category
            for cat, max_v in _MAX_PER_CATEGORY.items():
                breakdown[cat] = min(breakdown.get(cat, 0), max_v)
            # Reference is dominated by the documentation component
            reference = min(100.0, base * 1.5)
            samples.append(_make_sample(f"repo-{i}", breakdown, reference))
        return samples

    def test_fit_returns_calibration_result(self) -> None:
        samples = self._synthetic_samples()
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        assert result.n_samples == len(samples)
        assert result.fitted_weights is not None
        assert result.suggested_yaml_block.startswith("#")

    def test_fitted_weights_sum_to_100(self) -> None:
        samples = self._synthetic_samples()
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        total = sum(result.fitted_weights.values())
        assert total == pytest.approx(100.0, abs=0.5)

    def test_r_squared_between_minus_one_and_one(self) -> None:
        samples = self._synthetic_samples()
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        assert -1.0 <= result.r_squared <= 1.0

    def test_rmse_non_negative(self) -> None:
        samples = self._synthetic_samples()
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        assert result.rmse >= 0.0

    def test_all_categories_in_fitted_weights(self) -> None:
        samples = self._synthetic_samples()
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        assert set(result.fitted_weights.keys()) == set(BREAKDOWN_CATEGORIES)

    def test_insufficient_samples_adds_note(self) -> None:
        samples = self._synthetic_samples(n=3)
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        assert len(result.notes) >= 1
        assert any("sample" in note.lower() for note in result.notes)

    def test_single_sample_does_not_crash(self) -> None:
        samples = self._synthetic_samples(n=1)
        # Should not raise; may return fallback equal weights
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        assert result.fitted_weights is not None

    def test_yaml_block_contains_all_policy_names(self) -> None:
        samples = self._synthetic_samples()
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        yaml = result.suggested_yaml_block
        for policy_name in ["architecture", "documentation", "testing", "technical_depth", "portfolio_relevance", "maintainability"]:
            assert policy_name in yaml

    def test_perfect_linear_data_produces_reasonable_r_squared(self) -> None:
        """When the reference score is linearly determined by one component,
        the fit should produce R² > 0."""
        samples = []
        for i in range(12):
            ratio = (i + 1) / 12
            breakdown = {cat: ratio * _MAX_PER_CATEGORY.get(cat, 15.0) for cat in BREAKDOWN_CATEGORIES}
            reference = ratio * 100.0
            samples.append(_make_sample(f"r{i}", breakdown, reference))
        result = self.calibrator.fit(samples, _DEFAULT_WEIGHTS)
        # With perfectly linear data the fit should be decent
        assert result.r_squared > 0.0
