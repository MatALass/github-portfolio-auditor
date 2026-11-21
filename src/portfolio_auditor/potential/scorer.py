"""Score the portfolio *potential* of a repository for a target role.

The base ``ScoringEngine`` answers "how good is this repo today?". This module
answers "how good can it become for this role, and at what cost?". Each
component is a 0..1 value with a short human-readable reason so the final
number can be argued with.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from portfolio_auditor.potential.policy import PotentialPolicy, RepoOverride
from portfolio_auditor.potential.profiler import RepoProfile


@dataclass(slots=True)
class PotentialScore:
    full_name: str
    name: str
    potential: float  # 0..100
    current_level: float  # 0..100, base audit score
    upside: float  # potential - current_level, can be negative
    components: dict[str, float]
    effort_units: float
    effort_items: list[str]
    primary_domain: str | None
    secondary_domains: list[str]
    theme: str
    eligible: bool
    exclusion_reason: str | None = None
    merge_into: str | None = None
    note: str | None = None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "name": self.name,
            "potential": self.potential,
            "current_level": self.current_level,
            "upside": self.upside,
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "effort_units": self.effort_units,
            "effort_items": self.effort_items,
            "primary_domain": self.primary_domain,
            "secondary_domains": self.secondary_domains,
            "theme": self.theme,
            "eligible": self.eligible,
            "exclusion_reason": self.exclusion_reason,
            "merge_into": self.merge_into,
            "note": self.note,
            "reasons": self.reasons,
        }


class PotentialScorer:
    def __init__(self, policy: PotentialPolicy) -> None:
        self.policy = policy
        self._weights = policy.weights.normalised()

    def score(
        self,
        profile: RepoProfile,
        current_score: float,
        override: RepoOverride | None = None,
    ) -> PotentialScore:
        override = override or RepoOverride()
        strengths = dict(profile.domain_strength)
        primary = override.primary_domain or profile.primary_domain
        if override.primary_domain and override.primary_domain in strengths:
            # a human correction should win the argmax without erasing evidence
            strengths[override.primary_domain] = max(
                strengths[override.primary_domain], max(strengths.values(), default=0) + 0.01
            )
        theme = override.theme or profile.theme

        relevance = self._relevance(strengths)
        realness = min(
            1.0,
            max(
                0.0,
                profile.realness_raw / self.policy.realness.saturation + override.realness_bonus,
            ),
        )
        substance = self._substance(profile)
        current = max(0.0, min(1.0, current_score / 100))
        effort, effort_items = self._effort(profile, override)
        feasibility = max(0.0, 1.0 - effort / self.policy.effort.max_effort)
        recency = self._recency(profile.days_since_commit)

        components = {
            "role_relevance": relevance,
            "realness": realness,
            "substance": substance,
            "current_level": current,
            "feasibility": feasibility,
            "recency": recency,
        }
        potential = round(100 * sum(self._weights[k] * v for k, v in components.items()), 2)

        eligible, reason = self._eligibility(profile, override, relevance)
        secondary = [d for d in self._ranked(strengths) if d != primary][:2]

        return PotentialScore(
            full_name=profile.full_name,
            name=profile.name,
            potential=potential,
            current_level=round(current_score, 2),
            upside=round(potential - current_score, 2),
            components=components,
            effort_units=effort,
            effort_items=effort_items,
            primary_domain=primary,
            secondary_domains=[d for d in secondary if strengths.get(d, 0) >= 0.25],
            theme=theme,
            eligible=eligible,
            exclusion_reason=reason,
            merge_into=override.merge_into,
            note=override.note,
            reasons=self._reasons(profile, components, primary),
        )

    # ---------------------------------------------------------------- pieces
    def _relevance(self, strengths: dict[str, float]) -> float:
        weighted = sorted(
            (s * self.policy.domains[d].role_weight for d, s in strengths.items()),
            reverse=True,
        )
        if not weighted:
            return 0.0
        # best domain counts fully, the next two add breadth with diminishing value
        value = weighted[0] + 0.25 * sum(weighted[1:3])
        return min(1.0, value)

    @staticmethod
    def _ranked(strengths: dict[str, float]) -> list[str]:
        return [
            d for d, s in sorted(strengths.items(), key=lambda kv: kv[1], reverse=True) if s > 0
        ]

    def _substance(self, profile: RepoProfile) -> float:
        full = self.policy.substance.full_credit_code_kb
        # notebooks are bulky (outputs, base64 images): count them, but lightly
        effective_kb = profile.code_kb + 8 * min(profile.notebook_count, 10)
        if effective_kb <= 0:
            return 0.0
        return min(1.0, math.log1p(effective_kb) / math.log1p(full))

    def _effort(self, p: RepoProfile, override: RepoOverride) -> tuple[float, list[str]]:
        rule = self.policy.effort
        items: list[tuple[str, float]] = []
        if not p.has_readme:
            items.append(("README à écrire", rule.missing_readme))
        elif p.readme_words < rule.readme_min_words:
            items.append(("README trop court", rule.thin_readme))
        if not p.has_tests:
            items.append(("pas de tests", rule.missing_tests))
        if not p.has_ci:
            items.append(("pas de CI", rule.missing_ci))
        if not (p.has_visuals or p.has_demo_link):
            items.append(("aucune capture ni démo", rule.missing_visuals))
        if p.notebook_only:
            items.append(("analyse uniquement en notebooks", rule.notebook_only))
        if not p.has_package_layout:
            items.append(("structure plate (pas de src/)", rule.flat_layout))
        if p.tracked_kb > rule.heavy_repo_kb:
            items.append(("dépôt lourd (données ou sorties versionnées)", rule.heavy_repo))
        if p.days_since_commit > rule.stale_days:
            items.append(("contexte ancien", rule.stale))
        if p.personal_data_files:
            items.append(("données personnelles versionnées", rule.personal_data_tracked))
        for label, units in override.extra_effort.items():
            items.append((label, units))
        total = round(sum(v for _, v in items), 2)
        return total, [label for label, _ in items]

    def _recency(self, days: int) -> float:
        r = self.policy.recency
        if days <= r.full_credit_days:
            return 1.0
        if days >= r.zero_credit_days:
            return 0.0
        return 1.0 - (days - r.full_credit_days) / (r.zero_credit_days - r.full_credit_days)

    def _eligibility(
        self, p: RepoProfile, override: RepoOverride, relevance: float
    ) -> tuple[bool, str | None]:
        if override.exclude:
            return False, override.exclude
        for pattern in self.policy.eligibility.exclude_name_patterns:
            if re.search(pattern, p.name):
                return False, f"nom exclu par la politique ({pattern})"
        if p.commit_count and p.owner_commit_share < self.policy.eligibility.min_owner_commit_share:
            return False, (
                f"travail majoritairement d'autres personnes "
                f"({p.owner_commit_share:.0%} des commits)"
            )
        if relevance < self.policy.selection.min_role_relevance:
            return False, "peu de compétences du métier visé dans ce dépôt"
        return True, None

    def _reasons(self, p: RepoProfile, c: dict[str, float], primary: str | None) -> list[str]:
        reasons: list[str] = []
        if primary:
            reasons.append(f"domaine principal : {self.policy.domains[primary].label}")
        if c["realness"] >= 0.5 and p.realness_evidence:
            reasons.append("données ou besoin réels : " + ", ".join(p.realness_evidence[:4]))
        if c["substance"] >= 0.8:
            reasons.append(f"beaucoup de travail déjà fait (~{p.code_kb:.0f} ko de code)")
        if c["feasibility"] >= 0.75:
            reasons.append("peu de travail restant pour le rendre présentable")
        if c["recency"] == 0:
            reasons.append("contexte à reprendre (dépôt ancien)")
        return reasons
