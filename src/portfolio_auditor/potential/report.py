"""Markdown report for the potential audit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from portfolio_auditor.potential.policy import PotentialPolicy

if TYPE_CHECKING:
    from portfolio_auditor.potential.runner import PotentialArtifacts
    from portfolio_auditor.potential.scorer import PotentialScore


def decision_for(score: PotentialScore, artifacts: PotentialArtifacts) -> str:
    pf = artifacts.portfolio
    if score.full_name in pf.featured:
        return "Mettre en avant"
    if score.full_name in pf.bench:
        return "Réserve"
    if score.merge_into:
        return f"Fusionner dans {score.merge_into}"
    if not score.eligible:
        return "Hors sélection"
    if score.full_name in pf.skipped_for_diversity:
        return "Doublon de sujet ou de compétence"
    return "Secondaire"


def _why(score: PotentialScore, artifacts: PotentialArtifacts) -> str:
    pf = artifacts.portfolio
    if not score.eligible:
        return score.exclusion_reason or ""
    if score.full_name in pf.skipped_for_diversity:
        return pf.skipped_for_diversity[score.full_name]
    if score.note:
        return score.note
    return "; ".join(score.reasons[:2])


def render_markdown_report(artifacts: PotentialArtifacts, policy: PotentialPolicy) -> str:
    by_name = {s.full_name: s for s in artifacts.scores}
    pf = artifacts.portfolio
    out: list[str] = []
    out.append(f"# Audit de potentiel du portfolio ({policy.target_role})")
    out.append("")
    out.append(
        f"Dépôts analysés : {len(artifacts.scores)}. Politique : potential_{policy.version}."
    )
    out.append("")
    out.append("## Sélection proposée")
    out.append("")
    for i, name in enumerate(pf.featured, 1):
        s = by_name[name]
        label = policy.domains[s.primary_domain].label if s.primary_domain else "?"
        out.append(f"{i}. **{s.name}** : {label} (thème {s.theme}, potentiel {s.potential:.0f})")
    if pf.bench:
        out.append("")
        out.append("Réserve : " + ", ".join(by_name[n].name for n in pf.bench))
    out.append("")
    covered = ", ".join(pf.covered_core_domains) or "aucun"
    missing = ", ".join(pf.missing_core_domains) or "aucun"
    out.append(f"Domaines clés couverts : {covered}. Manquants : {missing}.")
    out.append("")
    out.append("## Tous les dépôts")
    out.append("")
    out.append("| # | Dépôt | Potentiel | Actuel | Domaine | Thème | Décision | Pourquoi |")
    out.append("|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(artifacts.scores, 1):
        out.append(
            f"| {i} | {s.name} | {s.potential:.0f} | {s.current_level:.0f} | "
            f"{s.primary_domain or '-'} | {s.theme} | {decision_for(s, artifacts)} | "
            f"{_why(s, artifacts).replace('|', '/')} |"
        )
    out.append("")
    out.append("## Détail du choix glouton")
    out.append("")
    for step in pf.steps:
        cov = ", ".join(step.newly_covered) or "rien de nouveau"
        out.append(
            f"- {by_name[step.full_name].name} ({step.role}) : gain {step.gain:.1f}, "
            f"similarité {step.similarity:.2f}, couvre {cov}"
        )
    return "\n".join(out) + "\n"
