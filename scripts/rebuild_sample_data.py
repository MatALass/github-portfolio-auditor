import json
from pathlib import Path

sample = [
    {
        "name": "repo_auditor",
        "description": "Audit GitHub repositories",
        "html_url": "https://github.com/example/repo_auditor",
        "language": "Python",
        "topics": ["python", "cli", "github", "audit"],
        "private": False,
        "fork": False,
        "archived": False,
        "stargazers_count": 0,
        "forks_count": 0,
    }
]

out = Path("data/raw/github/repos_raw.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(sample, indent=2), encoding="utf-8")
print(f"Wrote {out}")
