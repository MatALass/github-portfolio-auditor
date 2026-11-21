"""Build ``RepoMetadata`` from repositories already cloned on disk.

The GitHub collector needs a valid token and network access. This collector
only needs the clones, which makes the audit reproducible offline and lets it
include private repositories cloned with other credentials.

Metadata that only GitHub knows (stars, visibility, homepage) can be supplied
through an optional inventory JSON file::

    [
      {"full_name": "owner/repo", "dir": "owner_repo", "private": false,
       "html_url": "https://github.com/owner/repo", "homepage": null}
    ]

Without an inventory, every sub-directory of ``clones_dir`` that contains a
``.git`` folder is treated as a repository owned by ``default_owner``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from portfolio_auditor.models.repo_metadata import RepoMetadata

# Extension -> GitHub-like language label. Kept short on purpose: it only has
# to be good enough to pick a primary language and feed domain detection.
EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".ipynb": "Jupyter Notebook",
    ".sql": "SQL",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".vue": "Vue",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".java": "Java",
    ".cs": "C#",
    ".r": "R",
    ".tmdl": "TMDL",
    ".dax": "DAX",
    ".gml": "GML",
    ".sh": "Shell",
    ".ps1": "PowerShell",
}

SKIPPED_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", ".next"}
)


@dataclass(slots=True, frozen=True)
class LocalRepoEntry:
    full_name: str
    path: Path
    private: bool = False
    html_url: str | None = None
    homepage: str | None = None
    description: str | None = None


class LocalCollector:
    def __init__(self, clones_dir: Path, default_owner: str | None = None) -> None:
        self.clones_dir = Path(clones_dir)
        self.default_owner = default_owner

    # ------------------------------------------------------------------ entries
    def discover(self, inventory_path: Path | None = None) -> list[LocalRepoEntry]:
        if inventory_path is not None:
            return self._entries_from_inventory(Path(inventory_path))
        if not self.default_owner:
            raise ValueError("default_owner is required when no inventory is given")
        entries = []
        for child in sorted(self.clones_dir.iterdir()):
            if (child / ".git").exists():
                entries.append(
                    LocalRepoEntry(full_name=f"{self.default_owner}/{child.name}", path=child)
                )
        return entries

    def _entries_from_inventory(self, inventory_path: Path) -> list[LocalRepoEntry]:
        raw = json.loads(inventory_path.read_text(encoding="utf-8"))
        entries: list[LocalRepoEntry] = []
        for item in raw:
            full_name = item["full_name"]
            directory = item.get("dir") or full_name.replace("/", "__")
            path = self.clones_dir / directory
            if not path.exists():
                continue
            entries.append(
                LocalRepoEntry(
                    full_name=full_name,
                    path=path,
                    private=bool(item.get("private", False)),
                    html_url=item.get("html_url"),
                    homepage=item.get("homepage"),
                    description=item.get("description"),
                )
            )
        return entries

    # ----------------------------------------------------------------- metadata
    def build_metadata(self, entry: LocalRepoEntry) -> RepoMetadata:
        owner, name = entry.full_name.split("/", 1)
        created, updated = self._git_dates(entry.path)
        languages = self.language_bytes(entry.path)
        primary = max(languages.items(), key=lambda kv: kv[1])[0] if languages else None
        stable_id = int(hashlib.sha1(entry.full_name.encode()).hexdigest()[:12], 16)
        html_url = entry.html_url or f"https://github.com/{entry.full_name}"
        return RepoMetadata.model_validate(
            {
                "id": stable_id,
                "name": name,
                "full_name": entry.full_name,
                "description": entry.description or self._readme_summary(entry.path),
                "size_kb": self._size_kb(entry.path),
                "owner": {"login": owner, "type": "User", "html_url": None},
                "flags": {"private": entry.private},
                "timestamps": {"created_at": created, "updated_at": updated, "pushed_at": updated},
                "links": {
                    "html_url": html_url,
                    "clone_url": f"{html_url}.git",
                    "homepage": entry.homepage,
                },
                "language": primary,
                "language_stats": {"languages": languages},
            }
        )

    def collect(self, inventory_path: Path | None = None) -> list[tuple[RepoMetadata, Path]]:
        return [(self.build_metadata(e), e.path) for e in self.discover(inventory_path)]

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def iter_files(root: Path):
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                children = list(current.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_dir():
                    if child.name not in SKIPPED_DIRS:
                        stack.append(child)
                elif child.is_file():
                    yield child

    @classmethod
    def language_bytes(cls, root: Path) -> dict[str, int]:
        totals: dict[str, int] = {}
        for file in cls.iter_files(root):
            language = EXTENSION_LANGUAGES.get(file.suffix.lower())
            if language is None:
                continue
            try:
                totals[language] = totals.get(language, 0) + file.stat().st_size
            except OSError:
                continue
        return totals

    @classmethod
    def _size_kb(cls, root: Path) -> int:
        total = 0
        for file in cls.iter_files(root):
            try:
                total += file.stat().st_size
            except OSError:
                continue
        return total // 1024

    @staticmethod
    def _git_dates(path: Path) -> tuple[datetime, datetime]:
        def run(*args: str) -> str:
            try:
                result = subprocess.run(
                    ["git", "-C", str(path), *args],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError):
                return ""
            return result.stdout.strip()

        last = run("log", "-1", "--format=%cI")
        first = run("log", "--reverse", "--format=%cI", "--max-parents=0")
        now = datetime.now(UTC)
        updated = datetime.fromisoformat(last) if last else now
        created = datetime.fromisoformat(first.splitlines()[0]) if first else updated
        return created, updated

    @staticmethod
    def _readme_summary(path: Path) -> str | None:
        for candidate in ("README.md", "readme.md", "README.MD", "Readme.md"):
            readme = path / candidate
            if readme.exists():
                text = readme.read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    line = line.strip()
                    if line and not line.startswith(("#", "!", "<", "[", "`", "|", ">", "-", "=")):
                        return line[:300]
        return None
