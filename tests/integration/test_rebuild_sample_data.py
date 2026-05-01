"""
Integration tests for scripts/rebuild_sample_data.py.

These tests actually run the script and verify the artifact it produces,
rather than just checking whether the file exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/rebuild_sample_data.py").resolve()


@pytest.mark.integration
def test_script_exists():
    assert SCRIPT.exists(), f"Expected script at {SCRIPT}"


@pytest.mark.integration
def test_script_runs_successfully(tmp_path, monkeypatch):
    """Script must exit 0 and write a valid JSON file under the tmp workspace."""
    monkeypatch.chdir(tmp_path)
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Script exited with {result.returncode}:\n{result.stderr}"


@pytest.mark.integration
def test_script_produces_valid_json(tmp_path, monkeypatch):
    """The artifact written by the script must be a non-empty JSON list."""
    monkeypatch.chdir(tmp_path)
    subprocess.run([sys.executable, str(SCRIPT)], check=True, capture_output=True)

    output_file = tmp_path / "data" / "raw" / "github" / "repos_raw.json"
    assert output_file.exists(), f"Expected output at {output_file}"

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list), "Output must be a JSON list"
    assert len(payload) > 0, "Output list must not be empty"


@pytest.mark.integration
def test_script_output_has_required_fields(tmp_path, monkeypatch):
    """Each entry in the output must carry the fields downstream code relies on."""
    monkeypatch.chdir(tmp_path)
    subprocess.run([sys.executable, str(SCRIPT)], check=True, capture_output=True)

    output_file = tmp_path / "data" / "raw" / "github" / "repos_raw.json"
    payload = json.loads(output_file.read_text(encoding="utf-8"))

    required_fields = {"name", "html_url", "language", "private", "fork", "archived"}
    for entry in payload:
        missing = required_fields - entry.keys()
        assert not missing, f"Entry missing fields {missing}: {entry}"
