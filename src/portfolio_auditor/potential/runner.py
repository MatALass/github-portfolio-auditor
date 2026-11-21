"""End-to-end potential audit on local clones.

local clones -> metadata -> base scanners + scoring (current level)
             -> profile -> potential score -> diverse selection -> prompts + report
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from portfolio_auditor.collectors.local.collector import LocalCollector
from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.potential.policy import (
    PotentialPolicy,
    RepoOverride,
    load_overrides,
    load_potential_policy,
)
from portfolio_auditor.potential.profiler import RepoProfile, RepoProfiler
from portfolio_auditor.potential.prompts import ImprovementPromptBuilder
from portfolio_auditor.potential.report import render_markdown_report
from portfolio_auditor.potential.scorer import PotentialScore, PotentialScorer
from portfolio_auditor.potential.selector import DiversePortfolio, DiverseSelector
from portfolio_auditor.scanners import (
    CiScanner,
    DeliveryCleanlinessScanner,
    DocumentationScanner,
    StructureScanner,
    TestingScanner,
)
from portfolio_auditor.scoring.engine import ScoringEngine

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PotentialArtifacts:
    profiles: dict[str, RepoProfile]
    scores: list[PotentialScore]
    portfolio: DiversePortfolio
    prompts: dict[str, str]


class PotentialRunner:
    def __init__(
        self,
        policy: PotentialPolicy | None = None,
        overrides: dict[str, RepoOverride] | None = None,
    ) -> None:
        self.policy = policy or load_potential_policy()
        self.overrides = overrides or {}
        self.scanners = [
            StructureScanner(),
            DocumentationScanner(),
            TestingScanner(),
            CiScanner(),
            DeliveryCleanlinessScanner(),
        ]
        self.engine = ScoringEngine()
        self.profiler = RepoProfiler(self.policy)
        self.scorer = PotentialScorer(self.policy)
        self.selector = DiverseSelector(self.policy)
        self.prompt_builder = ImprovementPromptBuilder(self.policy)

    @classmethod
    def from_paths(cls, policy_path: Path | None, overrides_path: Path | None) -> PotentialRunner:
        return cls(load_potential_policy(policy_path), load_overrides(overrides_path))

    def _override_for(self, repo: RepoMetadata) -> RepoOverride | None:
        return self.overrides.get(repo.full_name.lower()) or self.overrides.get(repo.name.lower())

    def scan(self, repo: RepoMetadata, path: Path) -> RepoScanResult:
        result = RepoScanResult(
            repo_name=repo.name, repo_full_name=repo.full_name, local_path=str(path)
        )
        for scanner in self.scanners:
            result.add_scanner_summary(scanner.scan(repo, path, result))
        return result

    def run(
        self,
        clones_dir: Path,
        inventory: Path | None = None,
        owner: str | None = None,
        now: datetime | None = None,
    ) -> PotentialArtifacts:
        now = now or datetime.now(UTC)
        collector = LocalCollector(clones_dir, default_owner=owner)
        profiles: dict[str, RepoProfile] = {}
        scores: list[PotentialScore] = []
        for repo, path in collector.collect(inventory):
            try:
                scan = self.scan(repo, path)
                base = self.engine.score(repo, scan)
                profile = self.profiler.profile(
                    repo,
                    path,
                    has_tests=scan.testing.has_tests,
                    has_ci=scan.ci.has_github_actions,
                    now=now,
                )
                score = self.scorer.score(profile, base.global_score, self._override_for(repo))
            except Exception:  # one broken repo must not stop the audit
                logger.exception("potential audit failed for %s", repo.full_name)
                continue
            profiles[repo.full_name] = profile
            scores.append(score)

        scores.sort(key=lambda s: s.potential, reverse=True)
        portfolio = self.selector.select(scores, profiles)
        prompts = self._prompts(scores, profiles, portfolio)
        return PotentialArtifacts(profiles, scores, portfolio, prompts)

    def _prompts(
        self,
        scores: list[PotentialScore],
        profiles: dict[str, RepoProfile],
        portfolio: DiversePortfolio,
    ) -> dict[str, str]:
        by_name = {s.full_name: s for s in scores}
        featured_names = [by_name[n].name for n in portfolio.featured]
        out: dict[str, str] = {}
        for idx, full_name in enumerate(portfolio.featured + portfolio.bench):
            score = by_name[full_name]
            if full_name in portfolio.featured:
                role = f"projet mis en avant n°{idx + 1} sur {len(portfolio.featured)}"
            else:
                role = "projet de réserve (à mettre en avant si un projet principal déçoit)"
            siblings = [n for n in featured_names if n != score.name]
            out[full_name] = self.prompt_builder.build(
                score, profiles[full_name], portfolio_role=role, siblings=siblings
            )
        return out

    def export(self, artifacts: PotentialArtifacts, output_dir: Path) -> Path:
        output_dir = Path(output_dir)
        prompts_dir = output_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "potential_scores.json").write_text(
            json.dumps([s.to_dict() for s in artifacts.scores], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (output_dir / "repo_profiles.json").write_text(
            json.dumps(
                {k: v.to_dict() for k, v in artifacts.profiles.items()},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (output_dir / "diverse_portfolio.json").write_text(
            json.dumps(artifacts.portfolio.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        for full_name, text in artifacts.prompts.items():
            (prompts_dir / f"{full_name.replace('/', '__')}.md").write_text(text, encoding="utf-8")
        report = output_dir / "potential_report.md"
        report.write_text(render_markdown_report(artifacts, self.policy), encoding="utf-8")
        return report
