from pathlib import Path


def test_sample_data_file_layout():
    path = Path("scripts/rebuild_sample_data.py")
    assert path.exists()
