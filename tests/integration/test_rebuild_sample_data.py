from pathlib import Path
import json


def test_sample_data_file_layout():
    path = Path("scripts/rebuild_sample_data.py")
    assert path.exists()
