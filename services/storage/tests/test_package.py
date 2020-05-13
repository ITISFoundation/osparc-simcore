# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
# W0621: Redefining name ... from outer scope
# pylint: disable=W0621

import subprocess

import pytest

from simcore_service_storage.cli import main


@pytest.fixture
def pylintrc(osparc_simcore_root_dir):
    pylintrc = osparc_simcore_root_dir / ".pylintrc"
    assert pylintrc.exists()
    return pylintrc


def test_run_pylint(pylintrc, package_dir):
    AUTODETECT = 0
    cmd = f"pylint --jobs={AUTODETECT} --rcfile {pylintrc} -v {package_dir}".split()
    pipes = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, _ = pipes.communicate()
    if pipes.returncode != 0:
        print(std_out.decode('utf-8'))
        assert False, "Pylint failed with error, check this test's stdout to fix it"


def test_main(here):  # pylint: disable=unused-variable
    with pytest.raises(SystemExit) as excinfo:
        main("--help".split())

    assert excinfo.value.code == 0
