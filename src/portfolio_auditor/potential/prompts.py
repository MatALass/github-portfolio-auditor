"""Write one improvement prompt per repository.

The prompt is meant to be pasted into an AI coding assistant (or followed by
hand). It states the role the repository plays in the portfolio, the facts the
audit found, the domain-specific targets and a definition of done, so the work
stays focused on what a recruiter will actually look at.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from portfolio_auditor.potential.policy import PotentialPolicy
from portfolio_auditor.potential.profiler import RepoProfile
from portfolio_auditor.potential.scorer import PotentialScore

_PLAYBOOK_PATH = Path(__file__).parent / "policies" / "playbooks_v1.yaml"


class ImprovementPromptBuilder:
    def __init__(self, policy: PotentialPolicy, playbook_path: Path | None = None) -> None:
        self.policy = policy
        data = yaml.safe_load((playbook_path or _PLAYBOOK_PATH).read_text(encoding="utf-8"))
        self.domains: dict[str, dict] = data.get("domains", {})
        self.effort_fixes: dict[str, str] = data.get("effort_fixes", {})

    def build(
        self,
        score: PotentialScore,
        profile: RepoProfile,
        *,
        portfolio_role: str,
        siblings: list[str] | None = None,
    ) -> str:
        primary = score.primary_domain
        playbook = self.domains.get(primary or "", {})
        label = self.policy.domains[primary].label if primary else "non déterminé"
        secondary = ", ".join(self.policy.domains[d].label for d in score.secondary_domains)

        lines: list[str] = []
        lines.append(f"# Audit d'amélioration : {score.name}")
        lines.append("")
        lines.append(
            f"Tu travailles sur le dépôt `{score.full_name}`. Objectif : le rendre présentable "
            f"dans mon portfolio de Data Analyst (CDI visé en septembre 2027)."
        )
        lines.append("")
        lines.append("## Rôle de ce projet dans le portfolio")
        lines.append(f"- Place : {portfolio_role}.")
        lines.append(f"- Compétence principale à démontrer : {label}.")
        if playbook.get("shows"):
            lines.append(
                f"- Ce que le recruteur doit comprendre en 30 secondes : je sais {playbook['shows']}."
            )
        if secondary:
            lines.append(f"- Compétences secondaires visibles : {secondary}.")
        if siblings:
            lines.append(
                "- Ne pas refaire ce que montrent déjà les autres projets mis en avant : "
                + ", ".join(siblings)
                + ". Insister sur ce qui rend celui-ci différent."
            )
        lines.append("")
        lines.append("## Constats de l'audit automatique")
        lines.append(
            f"- Niveau actuel : {score.current_level:.0f}/100 ; potentiel estimé : "
            f"{score.potential:.0f}/100."
        )
        lines.append(
            f"- Code : ~{profile.code_kb:.0f} ko, {profile.python_module_count} modules Python, "
            f"{profile.notebook_count} notebooks ; README : {profile.readme_words} mots."
        )
        facts = [
            ("tests", profile.has_tests),
            ("CI", profile.has_ci),
            ("captures ou démo", profile.has_visuals or profile.has_demo_link),
            ("layout src/", profile.has_package_layout),
        ]
        lines.append(
            "- Présent : "
            + (", ".join(n for n, ok in facts if ok) or "rien de tout ça")
            + " ; absent : "
            + (", ".join(n for n, ok in facts if not ok) or "rien")
            + "."
        )
        if score.note:
            lines.append(f"- Note : {score.note}")
        lines.append("")
        lines.append("## Travail demandé, dans cet ordre")
        lines.append(
            "1. Lis tout le dépôt et fais-moi un état des lieux en 10 lignes max : ce qui marche, "
            "ce qui est cassé, ce qui manque. Lance le projet et les tests s'il y en a. "
            "Attends ma validation avant de modifier quoi que ce soit."
        )
        step = 2
        for item in score.effort_items:
            fix = self.effort_fixes.get(item)
            if fix:
                lines.append(f"{step}. {fix}")
                step += 1
        for target in playbook.get("targets", []):
            lines.append(f"{step}. {target}")
            step += 1
        lines.append(
            f"{step}. Relance l'auditeur (`portfolio-auditor potential-run`) et montre-moi "
            "l'évolution du score."
        )
        lines.append("")
        lines.append("## Contraintes")
        lines.append(
            "- Donne le code complet des fichiers modifiés, ou des instructions pas à pas très précises."
        )
        lines.append(
            "- Architecture propre et durable : layout src/, configs séparées, tests, CI. "
            "Signale clairement tout point incertain plutôt que de le masquer."
        )
        lines.append(
            "- Rédaction dans ma voix (skill humaniser-texte), sans tiret cadratin. "
            "README en français, clair et concis."
        )
        if profile.private:
            lines.append(
                "- Le dépôt est privé : avant toute mise en public, vérifie qu'aucune donnée "
                "personnelle ou confidentielle n'est versionnée (historique git compris) et "
                "propose une version anonymisée ou synthétique des données."
            )
        lines.append(
            "- Pas de refonte gratuite : chaque changement doit rendre le projet plus lisible "
            "pour un recruteur data ou plus fiable."
        )
        lines.append("")
        lines.append("## Terminé quand")
        lines.append(
            "- Un recruteur comprend le problème, la méthode et le résultat chiffré en lisant "
            "le haut du README."
        )
        lines.append("- Le projet se lance en une commande documentée et les tests passent en CI.")
        lines.append("- Le score de l'auditeur a progressé et aucun bloquant ne reste.")
        return "\n".join(lines) + "\n"
