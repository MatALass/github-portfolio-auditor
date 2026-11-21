from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from portfolio_auditor.potential.policy import load_potential_policy


def make_git_repo(root: Path, files: dict[str, str], author: str = "MatALass") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    env_args = ["-c", f"user.name={author}", "-c", f"user.email={author.lower()}@example.com"]
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(root), *env_args, "commit", "-q", "-m", "init"],
        check=True,
    )
    return root


@pytest.fixture()
def policy():
    return load_potential_policy()
