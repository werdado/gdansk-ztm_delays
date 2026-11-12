import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from world import ArchiveBuilder, write_gtfs  # noqa: E402


@pytest.fixture
def world(tmp_path):
    archive = tmp_path / "archive"
    gtfs = tmp_path / "gtfs.zip"
    write_gtfs(gtfs)
    b = ArchiveBuilder(archive)
    b.add_boundaries()
    return b, gtfs, tmp_path / "out" / "dataset.sqlite"
