# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import argparse
import re
import unittest.mock as mock

import pytest
import yaml

from simcore_service_webserver.cli import parse, setup_parser
from simcore_service_webserver.resources import resources


@pytest.fixture("session")
def env_devel_file(osparc_simcore_root_dir):
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture("session")
def services_docker_compose_file(osparc_simcore_root_dir):
    dcpath = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert dcpath.exists()
    return dcpath

@pytest.fixture("session")
def devel_environ(env_devel_file):
    env_devel = {}
    with env_devel_file.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=")
                env_devel[key] = value
    return env_devel


@pytest.fixture("session")
def container_environ(services_docker_compose_file, devel_environ):
    """ Creates a dict with the environment variables
        inside of a webserver container
    """
    dc = dict()
    with services_docker_compose_file.open() as f:
        dc = yaml.safe_load(f)

    container_environ = {
        'SIMCORE_WEB_OUTDIR': 'home/scu/services/web/client' # defined in Dockerfile
    }

    environ_items =dc["services"]["webserver"]["environment"]
    MATCH = re.compile(r'\$\{(\w+)+')

    for item in environ_items:
        key, value = item.split("=")
        m = MATCH.match(value)
        if m:
            envkey = m.groups()[0]
            value = devel_environ[envkey]
        container_environ[key] = value

    return container_environ


@pytest.mark.parametrize("configfile", [str(n)
                            for n in resources.listdir("config")
                        ])
def test_config_files(configfile, container_environ):
    parser = setup_parser(argparse.ArgumentParser("test-parser"))

    with mock.patch('os.environ', container_environ):
        cmd = ["-c", configfile]
        config = parse(cmd, parser)

        for key, value in config.items():
            assert value!='None', "Use instead Null in {} for {}".format(configfile, key)

        # adds some defaults checks here
        assert config['smtp']['username'] is None
