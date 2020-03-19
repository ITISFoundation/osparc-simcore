# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from pathlib import Path

import pytest

import simcore_service_sidecar


current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def project_slug_dir():
    folder = current_dir.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_sidecar"))
    return folder


@pytest.fixture(scope="session")
def package_dir():
    dirpath = Path(simcore_service_sidecar.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(project_slug_dir):
    root_dir = project_slug_dir.parent.parent
    assert (
        root_dir and root_dir.exists()
    ), "Did you renamed or moved the integration folder under sidecar??"
    assert any(root_dir.glob("services/sidecar")), (
        "%s not look like rootdir" % root_dir
    )
    return root_dir