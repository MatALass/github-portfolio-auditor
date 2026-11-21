from __future__ import annotations

import json

import pytest
from tests.unit.potential.conftest import make_git_repo

from portfolio_auditor.potential.runner import PotentialRunner

pytestmark = pytest.mark.integration


def test_runner_end_to_end(tmp_path):
    clones = tmp_path / "clones"
    make_git_repo(
        clones / "me_sales-bi",
        {
            "README.md": "# Sales BI\nPower BI star schema on 12,500 orders.\n" + "word " * 400,
            "model/Sales.SemanticModel/definition/tables/Fact.tmdl": "table Fact",
            "model/Sales.pbip": "{}",
            "src/pkg/__init__.py": "",
            "tests/test_x.py": "def test_x():\n    assert True\n",
        },
    )
    make_git_repo(
        clones / "me_game",
        {"README.md": "# Game\nA pygame arcade game.", "main.py": "import pygame\n" + "#" * 500},
    )
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            [
                {"full_name": "me/sales-bi", "dir": "me_sales-bi"},
                {"full_name": "me/game", "dir": "me_game", "private": True},
            ]
        ),
        encoding="utf-8",
    )
    runner = PotentialRunner()
    artifacts = runner.run(clones, inventory=inventory)
    assert {s.name for s in artifacts.scores} == {"sales-bi", "game"}
    assert artifacts.portfolio.featured == ["me/sales-bi"]
    report = runner.export(artifacts, tmp_path / "out")
    text = report.read_text(encoding="utf-8")
    assert "| game |" in text and "Mettre en avant" in text
    assert (tmp_path / "out" / "prompts" / "me__sales-bi.md").exists()
