# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
# W0621: Redefining name ... from outer scope
# pylint: disable=W0621

import pytest
import subprocess

from simcore_service_webserver.cli import main


@pytest.fixture
def pylintrc(osparc_simcore_root_dir):
    pylintrc = osparc_simcore_root_dir / ".pylintrc"
    assert pylintrc.exists()
    return pylintrc

def test_run_pylint(pylintrc, package_dir):
    cmd = 'pylint -j 2 --rcfile {} -v {}'.format(pylintrc, package_dir)
    assert subprocess.check_call(cmd.split()) == 0


def test_main(here): # pylint: disable=unused-variable
    with pytest.raises(SystemExit) as excinfo:
        main("--help".split())

    assert excinfo.value.code == 0
