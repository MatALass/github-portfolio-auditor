"""
tests/unit/test_decision_maps.py

Unit tests for:
- DECISION_LABEL_MAP  — every known decision key has a display label
- DECISION_GROUP_MAP  — every known decision key has a group
- _load_action_impact_rules — YAML loader produces a valid ruleset

These are small regression guards: if the decision set is extended in the
pipeline without updating the dashboard maps, these tests fail immediately.
"""

from __future__ import annotations

from portfolio_auditor.dashboard.data_loader import DECISION_GROUP_MAP, DECISION_LABEL_MAP
from portfolio_auditor.dashboard.optimizer import ACTION_IMPACT_RULES, _load_action_impact_rules

# ---------------------------------------------------------------------------
# Known decision keys — extend this set when new decisions are added upstream
# ---------------------------------------------------------------------------

KNOWN_DECISIONS = {
    "FEATURE_NOW",
    "KEEP_AND_IMPROVE",
    "MERGE_OR_REPOSITION",
    "ARCHIVE_PUBLIC",
    "MAKE_PRIVATE",
}

VALID_GROUPS = {"keep", "improve", "discard"}


# ---------------------------------------------------------------------------
# DECISION_LABEL_MAP
# ---------------------------------------------------------------------------


class TestDecisionLabelMap:
    def test_all_known_decisions_have_a_label(self) -> None:
        missing = KNOWN_DECISIONS - DECISION_LABEL_MAP.keys()
        assert not missing, f"DECISION_LABEL_MAP is missing entries for: {missing}"

    def test_labels_are_non_empty_strings(self) -> None:
        for key, label in DECISION_LABEL_MAP.items():
            assert isinstance(label, str) and label.strip(), (
                f"DECISION_LABEL_MAP[{key!r}] is blank or not a string"
            )

    def test_no_unknown_decisions_in_map(self) -> None:
        """Warn when new decisions appear in the map but not in the known set."""
        extra = DECISION_LABEL_MAP.keys() - KNOWN_DECISIONS
        assert not extra, (
            f"DECISION_LABEL_MAP contains unknown decision keys: {extra}. "
            "Add them to KNOWN_DECISIONS in this test file."
        )


# ---------------------------------------------------------------------------
# DECISION_GROUP_MAP
# ---------------------------------------------------------------------------


class TestDecisionGroupMap:
    def test_all_known_decisions_have_a_group(self) -> None:
        missing = KNOWN_DECISIONS - DECISION_GROUP_MAP.keys()
        assert not missing, f"DECISION_GROUP_MAP is missing entries for: {missing}"

    def test_groups_are_valid_values(self) -> None:
        for key, group in DECISION_GROUP_MAP.items():
            assert group in VALID_GROUPS, (
                f"DECISION_GROUP_MAP[{key!r}] = {group!r} is not a valid group. "
                f"Valid groups: {VALID_GROUPS}"
            )

    def test_label_map_and_group_map_have_same_keys(self) -> None:
        assert DECISION_LABEL_MAP.keys() == DECISION_GROUP_MAP.keys(), (
            "DECISION_LABEL_MAP and DECISION_GROUP_MAP must have identical key sets. "
            f"Diff: {DECISION_LABEL_MAP.keys() ^ DECISION_GROUP_MAP.keys()}"
        )


# ---------------------------------------------------------------------------
# ACTION_IMPACT_RULES / YAML loader
# ---------------------------------------------------------------------------


class TestActionImpactRules:
    def test_rules_loaded_is_a_dict(self) -> None:
        assert isinstance(ACTION_IMPACT_RULES, dict)

    def test_rules_are_not_empty(self) -> None:
        assert len(ACTION_IMPACT_RULES) > 0, "ACTION_IMPACT_RULES is empty — check YAML path"

    def test_each_rule_has_required_keys(self) -> None:
        required = {"penalty_codes", "fallback_points", "effort_units", "category"}
        for text, rule in ACTION_IMPACT_RULES.items():
            missing = required - rule.keys()
            assert not missing, f"Rule {text!r} is missing keys: {missing}"

    def test_penalty_codes_are_sets(self) -> None:
        for text, rule in ACTION_IMPACT_RULES.items():
            assert isinstance(rule["penalty_codes"], set), (
                f"Rule {text!r}: penalty_codes must be a set, got {type(rule['penalty_codes'])}"
            )

    def test_effort_units_are_positive(self) -> None:
        for text, rule in ACTION_IMPACT_RULES.items():
            assert rule["effort_units"] > 0, (
                f"Rule {text!r}: effort_units must be > 0, got {rule['effort_units']}"
            )

    def test_loader_returns_empty_dict_on_missing_file(self, tmp_path) -> None:
        result = _load_action_impact_rules(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_loader_parses_yaml_correctly(self, tmp_path) -> None:
        yaml_content = """\
actions:
  - text: "Write tests."
    penalty_codes:
      - NO_TESTS_DETECTED
    fallback_points: 5.0
    effort_units: 3.0
    category: testing
"""
        path = tmp_path / "rules.yaml"
        path.write_text(yaml_content, encoding="utf-8")
        result = _load_action_impact_rules(path)

        assert "Write tests." in result
        rule = result["Write tests."]
        assert rule["penalty_codes"] == {"NO_TESTS_DETECTED"}
        assert rule["fallback_points"] == 5.0
        assert rule["effort_units"] == 3.0
        assert rule["category"] == "testing"
