"""Pick a portfolio that is strong AND varied.

Ranking by potential alone tends to return three projects on the same subject
built with the same stack. The selector is a greedy maximiser of potential
under three constraints:

* at most ``max_per_theme`` repositories per subject theme,
* at most ``max_per_primary_domain`` repositories per primary skill domain,
* a multiplicative penalty for skill-profile similarity to what is already
  picked, and a bonus for each core domain a candidate covers for the first time.

Greedy is not optimal in general, but with a handful of slots it is easy to
explain ("this one was picked because it added SQL, which nothing else had").
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from portfolio_auditor.potential.policy import PotentialPolicy
from portfolio_auditor.potential.profiler import RepoProfile
from portfolio_auditor.potential.scorer import PotentialScore


@dataclass(slots=True)
class SelectionStep:
    full_name: str
    gain: float
    potential: float
    similarity: float
    newly_covered: list[str]
    role: str  # "featured" | "bench"

    def to_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "gain": round(self.gain, 2),
            "potential": self.potential,
            "similarity_to_selection": round(self.similarity, 3),
            "newly_covered_core_domains": self.newly_covered,
            "role": self.role,
        }


@dataclass(slots=True)
class DiversePortfolio:
    featured: list[str]
    bench: list[str]
    steps: list[SelectionStep]
    covered_core_domains: list[str]
    missing_core_domains: list[str]
    skipped_for_diversity: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "featured": self.featured,
            "bench": self.bench,
            "steps": [s.to_dict() for s in self.steps],
            "covered_core_domains": self.covered_core_domains,
            "missing_core_domains": self.missing_core_domains,
            "skipped_for_diversity": self.skipped_for_diversity,
        }


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class DiverseSelector:
    def __init__(self, policy: PotentialPolicy) -> None:
        self.policy = policy
        self.rule = policy.selection

    def select(
        self,
        scores: list[PotentialScore],
        profiles: dict[str, RepoProfile],
    ) -> DiversePortfolio:
        min_weight = self.rule.min_primary_role_weight
        pool = [
            s
            for s in scores
            if s.eligible
            and not s.merge_into
            and s.primary_domain is not None
            and self.policy.domains[s.primary_domain].role_weight >= min_weight
        ]
        picked: list[PotentialScore] = []
        steps: list[SelectionStep] = []
        covered: set[str] = set()
        skipped: dict[str, str] = {}
        total = self.rule.featured_count + self.rule.bench_count

        while pool and len(picked) < total:
            best: tuple[float, PotentialScore, float, list[str]] | None = None
            for cand in pool:
                blocked = self._blocked(cand, picked)
                if blocked:
                    skipped.setdefault(cand.full_name, blocked)
                    continue
                vector = self._vector(cand, profiles)
                sim = max((cosine(vector, self._vector(p, profiles)) for p in picked), default=0.0)
                newly = self._core_covered(cand, profiles) - covered
                gain = (
                    cand.potential
                    * (1 - self.rule.domain_similarity_penalty * sim)
                    * (1 + self.rule.coverage_bonus * len(newly))
                )
                if best is None or gain > best[0]:
                    best = (gain, cand, sim, sorted(newly))
            if best is None:
                break
            gain, cand, sim, newly = best
            role = "featured" if len(picked) < self.rule.featured_count else "bench"
            picked.append(cand)
            covered.update(newly)
            steps.append(SelectionStep(cand.full_name, gain, cand.potential, sim, newly, role))
            pool.remove(cand)
            skipped.pop(cand.full_name, None)

        featured = [s.full_name for s in steps if s.role == "featured"]
        bench = [s.full_name for s in steps if s.role == "bench"]
        # what a featured project covers, not the bench
        featured_cover: set[str] = set()
        for s in picked[: self.rule.featured_count]:
            featured_cover |= self._core_covered(s, profiles)
        core = self.rule.core_domains
        return DiversePortfolio(
            featured=featured,
            bench=bench,
            steps=steps,
            covered_core_domains=[d for d in core if d in featured_cover],
            missing_core_domains=[d for d in core if d not in featured_cover],
            skipped_for_diversity={
                k: v for k, v in skipped.items() if k not in featured and k not in bench
            },
        )

    # ---------------------------------------------------------------- helpers
    def _blocked(self, cand: PotentialScore, picked: list[PotentialScore]) -> str | None:
        same_theme = [p for p in picked if p.theme == cand.theme and cand.theme != "other"]
        if len(same_theme) >= self.rule.max_per_theme:
            return f"même thème « {cand.theme} » que {same_theme[0].name}"
        same_domain = [p for p in picked if p.primary_domain == cand.primary_domain]
        if cand.primary_domain and len(same_domain) >= self.rule.max_per_primary_domain:
            names = ", ".join(p.name for p in same_domain)
            return f"domaine « {cand.primary_domain} » déjà pris par {names}"
        return None

    @staticmethod
    def _vector(score: PotentialScore, profiles: dict[str, RepoProfile]) -> dict[str, float]:
        # Squaring sharpens the profile: shared weak signals (every data repo
        # has a bit of "pipeline") matter less than each repo's strong domains.
        profile = profiles.get(score.full_name)
        return {k: v * v for k, v in profile.domain_strength.items()} if profile else {}

    def _core_covered(self, score: PotentialScore, profiles: dict[str, RepoProfile]) -> set[str]:
        profile = profiles.get(score.full_name)
        core = set(self.rule.core_domains)
        out = {score.primary_domain} & core if score.primary_domain else set()
        if profile:
            threshold = self.rule.core_coverage_min_strength
            out |= {d for d, s in profile.domain_strength.items() if s >= threshold and d in core}
        return out
