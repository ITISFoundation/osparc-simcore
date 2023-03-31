# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def requirements_folder(project_slug_dir: Path) -> Path:
    reqs_dir = project_slug_dir / "requirements"
    assert reqs_dir.exists()
    assert any(reqs_dir.glob("_*.txt"))
    return reqs_dir


def test_dask_requirements_in_sync(requirements_folder: Path):
    """If this test fails, do update requirements to re-sync all listings"""

    REQS_ENTRY_REGEX = re.compile(r"(\w+)==([\.\w]+)")
    NameVersionTuple = tuple[str, str]

    def get_reqs(fname: str) -> set[NameVersionTuple]:
        return set(REQS_ENTRY_REGEX.findall((requirements_folder / fname).read_text()))

    base_reqs = get_reqs("_base.txt")
    distributed_reqs = get_reqs("_dask-distributed.txt")

    assert base_reqs
    assert distributed_reqs

    assert distributed_reqs.issubset(base_reqs)
