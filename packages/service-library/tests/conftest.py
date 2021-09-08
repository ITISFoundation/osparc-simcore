# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import sys
from pathlib import Path
from typing import Dict

import pytest
import servicelib

pytest_plugins = [
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(servicelib.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("packages/service-library")), (
        "%s not look like rootdir" % root_dir
    )
    return root_dir
