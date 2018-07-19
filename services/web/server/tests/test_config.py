import inspect
import pathlib
import logging
import os

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


@pytest.fixture(scope="module")
def _environ():
    pg_config = scm.DbConfig()

    prev = None
    #pylint: disable=W0212
    if "POSTGRES_ENDPOINT" in os.environ:
        prev = os.environ["POSTGRES_ENDPOINT"]
    os.environ.putenv("POSTGRES_ENDPOINT", pg_config._url)
    yield os.environ

    if prev:
        os.environ["POSTGRES_ENDPOINT"] = prev
    else:
        del os.environ["POSTGRES_ENDPOINT"]

def test_env_config(_environ):
    pg_config = scm.DbConfig()
    config = scm.get_config()
    #pylint: disable=W0212
    assert config["postgres"]["user"] == pg_config._user
