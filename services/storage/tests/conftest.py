# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
#
# pylint: disable=W0621
import sys

import pytest

from pathlib import Path
import simcore_service_storage

@pytest.fixture
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture
def package_dir(here):
    dirpath = Path(simcore_service_storage.__file__).parent
    assert dirpath.exists()
    return dirpath
