# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
# W0621: Redefining name ... from outer scope
# pylint: disable=W0621

import pytest

from simcore_service_storage.cli import main


def test_main(here): # pylint: disable=unused-variable
    with pytest.raises(SystemExit) as excinfo:
        main("--help".split())
    
    assert excinfo.value.code == 0
    