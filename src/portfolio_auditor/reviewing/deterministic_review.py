from __future__ import annotations

from portfolio_auditor.models.portfolio_decision import PortfolioDecision
from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.models.repo_review import RepoReview
from portfolio_auditor.models.repo_scan import RepoScanResult
from portfolio_auditor.models.repo_score import RepoScore


class DeterministicReviewer:
    """
    Deterministic review layer that converts scan + score artifacts into:
    - strengths
    - weaknesses
    - blockers
    - quick wins
    - priority actions
    - final portfolio decision

    This layer must remain explainable and evidence-based.
    """

    def review(
        self,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> RepoReview:
        review = RepoReview(
            repo_name=repo.name,
            repo_full_name=repo.full_name,
        )

        review.executive_summary = self._build_executive_summary(repo, scan, score)
        review.recruiter_signal = self._build_recruiter_signal(repo, scan, score)

        self._populate_strengths(review, repo, scan, score)
        self._populate_weaknesses(review, repo, scan, score)
        self._populate_blockers(review, repo, scan, score)
        self._populate_quick_wins(review, repo, scan, score)
        self._populate_priority_actions(review, repo, scan, score)

        decision = self._decide(repo, scan, score)
        review.portfolio_decision = decision
        review.portfolio_rationale = self._build_portfolio_rationale(decision, repo, scan, score)

        return review

    def _build_executive_summary(
        self,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> str:
        language = repo.language or repo.language_stats.primary_language or "unknown"
        label = score.score_label

        if score.global_score >= 85:
            quality_text = "This repository already shows strong portfolio quality and professional delivery potential."
        elif score.global_score >= 75:
            quality_text = "This repository is strong overall, with a good technical base and a few improvement opportunities."
        elif score.global_score >= 60:
            quality_text = "This repository is promising but still needs several improvements before it should be featured confidently."
        elif score.global_score >= 45:
            quality_text = "This repository has some useful signals, but it is not yet strong enough for confident portfolio presentation."
        else:
            quality_text = "This repository is currently too weak or too incomplete to support a strong portfolio signal."

        return (
            f"{quality_text} Final score: {score.global_score:.2f}/100 ({label}). "
            f"Primary language: {language}. "
            f"Detected issues: {scan.issue_count}. "
            f"Confidence: {score.confidence:.2f}."
        )

    def _build_recruiter_signal(
        self,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> str:
        if score.global_score >= 85:
            return (
                "Strong recruiter signal. The repository appears structured, understandable, and credible "
                "as a featured engineering project."
            )
        if score.global_score >= 75:
            return (
                "Positive recruiter signal. The repository is credible, but a few delivery improvements "
                "would make it safer to highlight prominently."
            )
        if score.global_score >= 60:
            return (
                "Mixed recruiter signal. The project may have value, but the current delivery still creates doubt."
            )
        if score.global_score >= 45:
            return (
                "Weak recruiter signal. The repository may reflect effort, but the presentation and engineering "
                "quality are not yet convincing."
            )
        return (
            "Poor recruiter signal. In its current state, the repository is more likely to weaken than strengthen "
            "a portfolio."
        )

    def _populate_strengths(
        self,
        review: RepoReview,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> None:
        if scan.structure.has_src_dir:
            review.add_strength("Repository uses a dedicated src/ directory.", priority="medium")
        elif scan.structure.has_app_dir:
            review.add_strength("Repository uses a dedicated app/ directory.", priority="medium")

        if scan.structure.has_tests_dir:
            review.add_strength("Repository exposes a top-level tests/ directory.", priority="medium")

        if scan.documentation.has_readme:
            review.add_strength(
                f"README is present with approximately {scan.documentation.readme_word_count} words.",
                priority="high",
            )

        if scan.documentation.has_installation_section:
            review.add_strength("README includes installation or setup guidance.", priority="high")

        if scan.documentation.has_usage_section:
            review.add_strength("README includes usage instructions.", priority="high")

        if scan.documentation.has_architecture_section:
            review.add_strength("README documents the project structure or architecture.", priority="medium")

        if scan.testing.has_tests:
            review.add_strength(
                f"Automated tests detected ({scan.testing.test_file_count} test file(s)).",
                priority="high",
            )

        if scan.testing.detected_frameworks:
            review.add_strength(
                f"Testing framework(s) detected: {', '.join(scan.testing.detected_frameworks)}.",
                priority="medium",
            )

        if scan.ci.has_test_workflow:
            review.add_strength("CI appears to run automated tests.", priority="high")

        if scan.ci.has_lint_workflow:
            review.add_strength("CI includes linting or static validation checks.", priority="medium")

        if scan.cleanliness.has_gitignore:
            review.add_strength(".gitignore is present.", priority="low")

        if repo.links.homepage:
            review.add_strength("Repository exposes a homepage or demo URL.", priority="medium")

        if scan.documentation.has_screenshots_or_assets:
            review.add_strength("Documentation assets or screenshots were detected.", priority="medium")

        if score.global_score >= 85 and not review.strengths:
            review.add_strength("Repository achieves a strong overall portfolio score.", priority="high")

    def _populate_weaknesses(
        self,
        review: RepoReview,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> None:
        if not scan.documentation.has_readme:
            review.add_weakness("Repository does not include a README.", priority="high")

        if scan.documentation.has_readme and scan.documentation.readme_word_count < 120:
            review.add_weakness("README exists but remains too short for strong portfolio communication.", priority="high")

        if scan.documentation.has_readme and not scan.documentation.has_installation_section:
            review.add_weakness("README does not clearly explain installation or setup.", priority="medium")

        if scan.documentation.has_readme and not scan.documentation.has_usage_section:
            review.add_weakness("README does not clearly explain how to run or use the project.", priority="high")

        if not scan.structure.has_src_dir and not scan.structure.has_app_dir:
            review.add_weakness("Repository lacks a clearly identified main code directory.", priority="medium")

        if not scan.testing.has_tests:
            review.add_weakness("No automated tests were detected.", priority="high")
        elif scan.testing.test_file_count < 3:
            review.add_weakness("Detected test baseline is still very small.", priority="medium")

        if scan.testing.has_tests and not scan.ci.has_test_workflow:
            review.add_weakness("Tests exist but do not appear to be enforced in CI.", priority="medium")

        if not scan.ci.has_github_actions:
            review.add_weakness("No CI workflow was detected.", priority="medium")

        if not scan.cleanliness.has_gitignore:
            review.add_weakness(".gitignore is missing.", priority="medium")

        if scan.cleanliness.committed_build_artifacts:
            review.add_weakness("Generated build or cache artifacts appear to be committed.", priority="medium")

        if scan.cleanliness.oversized_files:
            review.add_weakness("Repository contains oversized files that reduce delivery quality.", priority="low")

        if not repo.description:
            review.add_weakness("Repository description is missing or empty on GitHub.", priority="low")

        if not repo.links.homepage and not repo.flags.has_pages:
            review.add_weakness("No homepage or demo link was detected.", priority="low")

    def _populate_blockers(
        self,
        review: RepoReview,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> None:
        if not scan.documentation.has_readme:
            review.add_blocker(
                "Missing README is a major blocker for both delivery and portfolio visibility.",
                priority="high",
            )

        if not scan.testing.has_tests:
            review.add_blocker(
                "Missing automated tests weakens engineering credibility significantly.",
                priority="high",
            )

        if scan.cleanliness.committed_virtualenv:
            review.add_blocker(
                "Committed virtual environment is a strong negative signal and should be removed before showcasing the repo.",
                priority="high",
            )

        if scan.cleanliness.committed_pycache:
            review.add_blocker(
                "Committed __pycache__ folders reduce professionalism and should be cleaned immediately.",
                priority="high",
            )

        if score.global_score < 45:
            review.add_blocker(
                "Overall repository quality is currently too low for safe portfolio presentation.",
                priority="high",
            )

    def _populate_quick_wins(
        self,
        review: RepoReview,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> None:
        if not scan.documentation.has_readme:
            review.add_quick_win("Write a complete README with setup, usage, and project purpose.", priority="high")

        if scan.documentation.has_readme and not scan.documentation.has_usage_section:
            review.add_quick_win("Add a usage section with concrete run examples.", priority="high")

        if scan.documentation.has_readme and not scan.documentation.has_installation_section:
            review.add_quick_win("Add installation/setup commands to the README.", priority="medium")

        if not scan.cleanliness.has_gitignore:
            review.add_quick_win("Add a proper .gitignore file.", priority="high")

        if scan.cleanliness.committed_pycache or scan.cleanliness.committed_pytest_cache:
            review.add_quick_win("Remove Python cache artifacts from version control.", priority="high")

        if scan.cleanliness.committed_build_artifacts or scan.cleanliness.committed_egg_info:
            review.add_quick_win("Delete generated build/package artifacts from the repository.", priority="medium")

        if not scan.ci.has_github_actions:
            review.add_quick_win("Add a basic GitHub Actions workflow for validation.", priority="medium")

        if scan.testing.has_tests and not scan.ci.has_test_workflow:
            review.add_quick_win("Connect the existing tests to CI.", priority="medium")

        if not repo.description:
            review.add_quick_win("Add a concise GitHub repository description.", priority="low")

        if not repo.links.homepage and scan.documentation.has_results_section:
            review.add_quick_win("Add a homepage or demo link if the project has a runnable output.", priority="low")

    def _populate_priority_actions(
        self,
        review: RepoReview,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> None:
        actions: list[tuple[str, str]] = []

        if not scan.documentation.has_readme:
            actions.append(("Write a complete README.", "high"))

        if scan.documentation.has_readme and not scan.documentation.has_usage_section:
            actions.append(("Document exactly how to run and use the project.", "high"))

        if not scan.testing.has_tests:
            actions.append(("Build a core automated test suite.", "high"))

        if scan.testing.has_tests and not scan.ci.has_test_workflow:
            actions.append(("Run automated tests in CI.", "high"))

        if not scan.structure.has_src_dir and not scan.structure.has_app_dir:
            actions.append(("Introduce a clearer source-code structure.", "medium"))

        if not scan.cleanliness.has_gitignore:
            actions.append(("Add and apply a proper .gitignore.", "high"))

        if scan.cleanliness.committed_virtualenv:
            actions.append(("Remove committed virtual environment folders.", "high"))

        if scan.cleanliness.committed_pycache:
            actions.append(("Delete committed __pycache__ directories.", "high"))

        if scan.cleanliness.committed_build_artifacts:
            actions.append(("Remove generated build/cache artifacts.", "medium"))

        if scan.cleanliness.oversized_files:
            actions.append(("Review large committed files and keep only necessary assets.", "medium"))

        if not repo.description:
            actions.append(("Add a concise GitHub description.", "low"))

        if not repo.links.homepage and scan.documentation.has_results_section:
            actions.append(("Expose a demo or homepage link when relevant.", "low"))

        if score.global_score >= 85 and not actions:
            actions.append(("Maintain the repository at its current quality level.", "low"))

        seen: set[str] = set()
        for text, priority in actions:
            if text not in seen:
                review.add_priority_action(text, priority=priority)
                seen.add(text)

    def _decide(
        self,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> PortfolioDecision:
        has_severe_delivery_problem = any(
            [
                scan.cleanliness.committed_virtualenv,
                not scan.documentation.has_readme,
                score.global_score < 45,
            ]
        )

        if score.global_score >= 85 and not review_has_major_blockers(scan):
            return PortfolioDecision.FEATURE_NOW

        if score.global_score >= 65 and not has_severe_delivery_problem:
            return PortfolioDecision.KEEP_AND_IMPROVE

        if score.global_score >= 50:
            return PortfolioDecision.MERGE_OR_REPOSITION

        if score.global_score >= 35:
            return PortfolioDecision.ARCHIVE_PUBLIC

        return PortfolioDecision.MAKE_PRIVATE

    def _build_portfolio_rationale(
        self,
        decision: PortfolioDecision,
        repo: RepoMetadata,
        scan: RepoScanResult,
        score: RepoScore,
    ) -> str:
        if decision == PortfolioDecision.FEATURE_NOW:
            return (
                "The repository is already strong enough to be featured directly: it shows credible structure, "
                "acceptable delivery quality, and a positive portfolio signal."
            )

        if decision == PortfolioDecision.KEEP_AND_IMPROVE:
            return (
                "The repository has real value and should remain visible, but targeted improvements would make it "
                "significantly safer and stronger for portfolio use."
            )

        if decision == PortfolioDecision.MERGE_OR_REPOSITION:
            return (
                "The repository contains some useful elements, but its current delivery is not strong enough on its own. "
                "It may be better improved, repositioned, or merged with a related project."
            )

        if decision == PortfolioDecision.ARCHIVE_PUBLIC:
            return (
                "The repository is currently too weak to feature, but it may still remain public as an archive or "
                "learning artifact if it does not confuse the portfolio narrative."
            )

        return (
            "The repository is currently more harmful than helpful for portfolio presentation and should generally be "
            "made private until it is substantially improved."
        )


def review_has_major_blockers(scan: RepoScanResult) -> bool:
    return any(
        [
            not scan.documentation.has_readme,
            scan.cleanliness.committed_virtualenv,
            scan.cleanliness.committed_pycache,
            not scan.testing.has_tests,
        ]
    )