"""Turn a local repository into a ``RepoProfile``: skill domains, theme and raw signals.

Detection is deliberately simple and explainable: every domain strength can be
traced back to the files, dependencies, keywords and paths that produced it
(see ``RepoProfile.domain_evidence``).
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from portfolio_auditor.collectors.local.collector import LocalCollector
from portfolio_auditor.models.repo_metadata import RepoMetadata
from portfolio_auditor.potential.policy import PotentialPolicy

CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".sql",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".c",
        ".cpp",
        ".cs",
        ".r",
        ".dax",
        ".vue",
    }
)
VISUAL_EXTENSIONS = frozenset({".png", ".gif", ".jpg", ".jpeg", ".webp", ".svg", ".mp4"})
DEMO_URL_PATTERN = re.compile(
    r"https?://[^\s)]+(streamlit\.app|github\.io|vercel\.app|netlify\.app|onrender\.com|"
    r"huggingface\.co/spaces|app\.powerbi\.com)",
    re.IGNORECASE,
)
OWNER_HINTS_DEFAULT = ("matalass", "mathieu", "alassoeur")
# 60,921 / 100 000 / 22309 ; years (1900-2099) are not figures
FIGURE_PATTERN = re.compile(
    r"(?<![\w.])\d{1,3}(?:[ ,\u202f\u00a0]\d{3})+(?![\w])|(?<![\w.])\d{4,}(?![\w])"
)
YEAR_PATTERN = re.compile(r"^(19|20)\d{2}$")


def count_figures(text: str) -> int:
    found = set()
    for match in FIGURE_PATTERN.findall(text):
        compact = re.sub(r"[ ,\u202f\u00a0]", "", match)
        if YEAR_PATTERN.match(compact):
            continue
        found.add(compact)
    return len(found)


@dataclass(slots=True)
class RepoProfile:
    full_name: str
    name: str
    private: bool
    code_kb: float
    notebook_count: int
    python_module_count: int
    readme_words: int
    has_readme: bool
    has_visuals: bool
    has_demo_link: bool
    has_case_study: bool
    has_tests: bool
    has_ci: bool
    has_package_layout: bool
    tracked_kb: int
    days_since_commit: int
    commit_count: int
    owner_commit_share: float
    dependencies: list[str]
    domain_strength: dict[str, float]
    domain_evidence: dict[str, list[str]]
    theme: str
    theme_hits: dict[str, int]
    realness_raw: float
    realness_evidence: list[str] = field(default_factory=list)
    personal_data_files: list[str] = field(default_factory=list)

    @property
    def notebook_only(self) -> bool:
        return self.notebook_count > 0 and self.python_module_count < 3

    @property
    def primary_domain(self) -> str | None:
        ranked = sorted(self.domain_strength.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked or ranked[0][1] <= 0:
            return None
        return ranked[0][0]

    def top_domains(self, n: int = 3, minimum: float = 0.25) -> list[str]:
        ranked = sorted(self.domain_strength.items(), key=lambda kv: kv[1], reverse=True)
        return [name for name, value in ranked[:n] if value >= minimum]

    def to_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "name": self.name,
            "private": self.private,
            "code_kb": round(self.code_kb, 1),
            "notebook_count": self.notebook_count,
            "python_module_count": self.python_module_count,
            "readme_words": self.readme_words,
            "has_visuals": self.has_visuals,
            "has_demo_link": self.has_demo_link,
            "has_case_study": self.has_case_study,
            "has_tests": self.has_tests,
            "has_ci": self.has_ci,
            "has_package_layout": self.has_package_layout,
            "tracked_kb": self.tracked_kb,
            "days_since_commit": self.days_since_commit,
            "commit_count": self.commit_count,
            "owner_commit_share": round(self.owner_commit_share, 2),
            "primary_domain": self.primary_domain,
            "domain_strength": {k: round(v, 2) for k, v in self.domain_strength.items() if v},
            "domain_evidence": self.domain_evidence,
            "theme": self.theme,
            "realness_raw": round(self.realness_raw, 2),
            "realness_evidence": self.realness_evidence,
            "personal_data_files": self.personal_data_files,
        }


def _notebook_to_lines(text: str) -> str:
    # In .ipynb JSON each source line looks like:  "import pandas as pd\n",
    return re.sub(r'^\s*"(\s*(?:from|import)\s)', r"\1", text, flags=re.MULTILINE)


@lru_cache(maxsize=4096)
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    escaped = re.escape(keyword.strip())
    right = r"(?![a-z0-9])" if len(keyword.strip()) <= 5 else ""
    return re.compile(rf"(?<![a-z0-9]){escaped}{right}")


def count_keyword(text: str, keyword: str) -> int:
    if keyword.endswith(" "):  # e.g. "tp " means the bare token
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(keyword.strip())}(?![a-z0-9])", text))
    return len(_keyword_pattern(keyword).findall(text))


class RepoProfiler:
    def __init__(self, policy: PotentialPolicy, owner_hints: tuple[str, ...] = OWNER_HINTS_DEFAULT):
        self.policy = policy
        self.owner_hints = tuple(h.lower() for h in owner_hints)

    def profile(
        self,
        repo: RepoMetadata,
        local_path: Path,
        *,
        has_tests: bool,
        has_ci: bool,
        now: datetime | None = None,
    ) -> RepoProfile:
        now = now or datetime.now(UTC)
        files = list(LocalCollector.iter_files(local_path))
        rel_paths = [f.relative_to(local_path).as_posix().lower() for f in files]

        code_bytes = 0
        notebooks = 0
        py_modules = 0
        visuals = 0
        tracked = 0
        ext_counts: dict[str, int] = {}
        for f, rel in zip(files, rel_paths, strict=True):
            suffix = f.suffix.lower()
            ext_counts[suffix] = ext_counts.get(suffix, 0) + 1
            try:
                size = f.stat().st_size
            except OSError:
                continue
            tracked += size
            if suffix in CODE_EXTENSIONS:
                code_bytes += size
            if suffix == ".py" and not rel.startswith(("test", "tests/")) and size > 300:
                py_modules += 1
            if suffix == ".ipynb":
                notebooks += 1
            if suffix in VISUAL_EXTENSIONS and any(
                part in rel for part in ("screenshot", "assets", "docs", "images", "img", "demo")
            ):
                visuals += 1

        readme_text = self._read_readme(local_path)
        readme_lower = readme_text.lower()
        corpus = f"{repo.name.lower().replace('-', ' ').replace('_', ' ')} {readme_lower} {(repo.description or '').lower()}"
        deps = sorted(self._dependencies(local_path))

        strength, evidence = self._domains(ext_counts, deps, corpus, rel_paths)
        theme, theme_hits = self._theme(repo.name.lower(), corpus)
        realness_raw, realness_evidence = self._realness(corpus, readme_text)

        commit_count, owner_share = self._git_authorship(local_path)
        personal_files = self._personal_data_files(local_path)
        last = repo.timestamps.pushed_at or repo.timestamps.updated_at
        days = max(0, (now - last).days)

        return RepoProfile(
            full_name=repo.full_name,
            name=repo.name,
            private=repo.flags.private,
            code_kb=code_bytes / 1024,
            notebook_count=notebooks,
            python_module_count=py_modules,
            readme_words=len(readme_text.split()),
            has_readme=bool(readme_text.strip()),
            has_visuals=visuals > 0 or "![" in readme_text or "<img" in readme_lower,
            has_demo_link=bool(DEMO_URL_PATTERN.search(readme_text)) or bool(repo.links.homepage),
            has_case_study=any(
                p in rel_paths for p in ("context.md", "docs/case_study.md", "case_study.md")
            ),
            has_tests=has_tests,
            has_ci=has_ci,
            has_package_layout=any(p.startswith(("src/", "app/")) for p in rel_paths)
            or any(p.endswith("/__init__.py") for p in rel_paths),
            tracked_kb=tracked // 1024,
            days_since_commit=days,
            commit_count=commit_count,
            owner_commit_share=owner_share,
            dependencies=deps,
            domain_strength=strength,
            domain_evidence=evidence,
            theme=theme,
            theme_hits=theme_hits,
            realness_raw=realness_raw,
            realness_evidence=realness_evidence,
            personal_data_files=personal_files,
        )

    # ---------------------------------------------------------------- domains
    def _domains(
        self,
        ext_counts: dict[str, int],
        deps: list[str],
        corpus: str,
        rel_paths: list[str],
    ) -> tuple[dict[str, float], dict[str, list[str]]]:
        dep_set = set(deps)
        strength: dict[str, float] = {}
        evidence: dict[str, list[str]] = {}
        for name, rule in self.policy.domains.items():
            raw = 0.0
            ev: list[str] = []
            for ext, weight in rule.extensions.items():
                n = ext_counts.get(ext, 0)
                if n:
                    # a few files are enough; more files add little
                    raw += weight * min(1.0, 0.5 + 0.1 * n)
                    ev.append(f"{n}x{ext}")
            for dep, weight in rule.dependencies.items():
                if dep in dep_set:
                    raw += weight
                    ev.append(f"dep:{dep}")
            kw_raw = 0.0
            for kw, weight in rule.keywords.items():
                hits = count_keyword(corpus, kw)
                if hits:
                    kw_raw += weight * min(1.5, 1.0 + 0.1 * (hits - 1))
                    ev.append(f"kw:{kw}x{hits}")
            raw += min(kw_raw, rule.keyword_cap * rule.saturation)
            for frag, weight in rule.paths.items():
                if any(frag in p for p in rel_paths):
                    raw += weight
                    ev.append(f"path:{frag}")
            strength[name] = round(min(1.0, max(0.0, raw) / rule.saturation), 4)
            if ev:
                evidence[name] = ev
        return strength, evidence

    def _theme(self, name: str, corpus: str) -> tuple[str, dict[str, int]]:
        hits: dict[str, int] = {}
        for theme, keywords in self.policy.themes.items():
            score = 0
            for kw in keywords:
                kw_l = kw.lower()
                score += count_keyword(corpus, kw_l)
                if kw_l in name.replace("-", " ").replace("_", " ") or kw_l in name:
                    score += 3
            if score:
                hits[theme] = score
        if not hits:
            return "other", hits
        return max(hits.items(), key=lambda kv: kv[1])[0], hits

    def _realness(self, corpus: str, readme: str) -> tuple[float, list[str]]:
        rule = self.policy.realness
        raw = 0.0
        ev: list[str] = []
        figures = count_figures(readme)
        if figures:
            raw += min(rule.quantified_cap, figures * rule.quantified_weight)
            ev.append(f"{figures} chiffres concrets")
        for kw, weight in self.policy.realness.keywords.items():
            if count_keyword(corpus, kw.lower()):
                raw += weight
                ev.append(kw.strip())
        return max(0.0, raw), ev

    # ------------------------------------------------------------------ files
    @staticmethod
    def _read_readme(path: Path) -> str:
        for candidate in ("README.md", "readme.md", "README.MD", "Readme.md", "README.rst"):
            readme = path / candidate
            if readme.exists():
                return readme.read_text(encoding="utf-8", errors="ignore")
        return ""

    @staticmethod
    def _dependencies(path: Path) -> set[str]:
        found: set[str] = set()
        name_re = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")
        for req in list(path.glob("requirements*.txt")) + list(path.glob("*/requirements*.txt")):
            for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith(("#", "-")):
                    continue
                m = name_re.match(line)
                if m:
                    found.add(m.group(1).lower())
        for pyproject in [path / "pyproject.toml", *path.glob("*/pyproject.toml")]:
            if not pyproject.exists():
                continue
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
            except tomllib.TOMLDecodeError:
                continue
            project = data.get("project", {})
            specs = list(project.get("dependencies", []))
            for group in project.get("optional-dependencies", {}).values():
                specs.extend(group)
            poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            specs.extend(poetry.keys())
            for spec in specs:
                m = name_re.match(str(spec))
                if m:
                    found.add(m.group(1).lower())
        for pkg in [path / "package.json", *path.glob("*/package.json")]:
            if not pkg.exists():
                continue
            try:
                data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
            except json.JSONDecodeError:
                continue
            for key in ("dependencies", "devDependencies"):
                found.update(k.lower() for k in (data.get(key) or {}))
        # Python imports catch notebooks and scripts with no dependency file.
        import_re = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
        aliases = {"sklearn": "scikit-learn", "bs4": "beautifulsoup4", "pygame": "pygame"}
        for f in LocalCollector.iter_files(path):
            if f.suffix not in (".py", ".ipynb"):
                continue
            try:
                if f.stat().st_size > 2_000_000:
                    continue
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for mod in import_re.findall(_notebook_to_lines(text)):
                mod = mod.lower()
                found.add(aliases.get(mod, mod))
        return found

    def _personal_data_files(self, path: Path) -> list[str]:
        """Tracked CSV files whose header looks like personal data.

        Only files known to git count: an ignored local file is not a leak.
        """
        rule = self.policy.personal_data
        if not rule.columns:
            return []
        try:
            listed = subprocess.run(
                ["git", "-C", str(path), "ls-files", "*.csv", "**/*.csv"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            ).stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            return []
        wanted = {c.lower() for c in rule.columns}
        flagged: list[str] = []
        for rel in sorted(set(listed)):
            try:
                with (path / rel).open(encoding="utf-8-sig", errors="ignore") as handle:
                    header = handle.readline()
            except OSError:
                continue
            tokens = {t.strip().strip('"').strip().lower() for t in re.split(r"[;,\t]", header)}
            if len(tokens & wanted) >= rule.min_hits:
                flagged.append(rel)
        return flagged

    def _git_authorship(self, path: Path) -> tuple[int, float]:
        try:
            out = subprocess.run(
                ["git", "-C", str(path), "log", "--format=%an|%ae"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return 0, 1.0
        lines = [line.lower() for line in out.splitlines() if line.strip()]
        if not lines:
            return 0, 1.0
        mine = sum(1 for line in lines if any(h in line for h in self.owner_hints))
        return len(lines), mine / len(lines)
