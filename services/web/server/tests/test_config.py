import inspect
import pathlib
import logging

import pytest

# under test
import server.config as scm

_LOGGER = logging.getLogger(__name__)

def test_valid_paths():
    all_paths = inspect.getmembers(scm, lambda m: isinstance(m, pathlib.Path))
    assert len(all_paths )!=0

    for (name, path) in all_paths:
        assert path.exists(), "Invalid path in variable {}".format(name)

def test_config_args():
    with pytest.raises(SystemExit) as einfo:
        argv = "--help".split()
        scm.get_config(argv)
    assert einfo.value.code == 0

def test_config_validation():
    argv = "--config config/server-test.yaml --check-config".split()

    with pytest.raises(SystemExit) as einfo:
        scm.get_config(argv)

    assert einfo.value.code == 0

def test_config_data():
    argv = "--config config/server-test.yaml".split()
    config = scm.get_config(argv)
    assert isinstance(config, dict)

    assert 'SIMCORE_CLIENT_OUTDIR' in config.keys()
