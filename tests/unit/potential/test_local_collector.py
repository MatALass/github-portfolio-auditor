from __future__ import annotations

import json

import pytest

from portfolio_auditor.collectors.local.collector import LocalCollector

from .conftest import make_git_repo

pytestmark = pytest.mark.unit


def test_discover_without_inventory_needs_owner(tmp_path):
    make_git_repo(tmp_path / "alpha", {"a.py": "print(1)\n"})
    (tmp_path / "not_a_repo").mkdir()
    with pytest.raises(ValueError):
        LocalCollector(tmp_path).discover()
    entries = LocalCollector(tmp_path, default_owner="me").discover()
    assert [e.full_name for e in entries] == ["me/alpha"]


def test_metadata_from_clone_and_inventory(tmp_path):
    make_git_repo(
        tmp_path / "me_beta",
        {"README.md": "# Beta\nTurns raw exports into a clean dataset.\n", "x.sql": "select 1;"},
    )
    inv = tmp_path / "inv.json"
    inv.write_text(
        json.dumps(
            [
                {"full_name": "me/beta", "dir": "me_beta", "private": True},
                {"full_name": "me/missing", "dir": "nope"},
            ]
        ),
        encoding="utf-8",
    )
    [(meta, path)] = LocalCollector(tmp_path).collect(inv)
    assert meta.full_name == "me/beta"
    assert meta.flags.private is True
    assert meta.language == "SQL"
    assert meta.description == "Turns raw exports into a clean dataset."
    assert path.name == "me_beta"
