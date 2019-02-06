# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import argparse
import importlib
import inspect
import re
import unittest.mock as mock
from pathlib import Path

import pytest
import yaml
from aiohttp import web

from simcore_service_webserver.cli import parse, setup_parser
from simcore_service_webserver.resources import resources
from simcore_service_webserver.application_config import create_schema


@pytest.fixture("session")
def app_config_schema():
    return create_schema()


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
def container_environ(services_docker_compose_file, devel_environ, osparc_simcore_root_dir):
    """ Creates a dict with the environment variables
        inside of a webserver container
    """
    dc = dict()
    with services_docker_compose_file.open() as f:
        dc = yaml.safe_load(f)

    container_environ = {
        'SIMCORE_WEB_OUTDIR': 'home/scu/services/web/client',  # defined in Dockerfile
        'OSPARC_SIMCORE_REPO_ROOTDIR': str(osparc_simcore_root_dir) # defined if pip install --edit (but not in travis!)
    }

    environ_items = dc["services"]["webserver"]["environment"]
    MATCH = re.compile(r'\$\{(\w+)+')

    for item in environ_items:
        key, value = item.split("=")
        m = MATCH.match(value)
        if m:
            envkey = m.groups()[0]
            value = devel_environ[envkey]
        container_environ[key] = value

    return container_environ


# TESTS ----------------------------------------------------------------------

@pytest.mark.parametrize("configfile", [str(n)
                                        for n in resources.listdir("config")
                                        ])
def test_correctness_under_environ(configfile, container_environ):
    parser = setup_parser(argparse.ArgumentParser("test-parser"))

    with mock.patch('os.environ', container_environ):
        cmd = ["-c", configfile]
        config = parse(cmd, parser)

        for key, value in config.items():
            assert value != 'None', "Use instead Null in {} for {}".format(
                configfile, key)

        # adds some defaults checks here
        assert config['smtp']['username'] is None


@pytest.fixture("session")
def app_subsystems(package_dir):
    """
        subsystem = all modules in package with a setup function
    """
    def is_py_module(path: Path) -> bool:
        return not path.name.startswith((".", "__")) and \
            ( path.suffix == ".py" or any(path.glob("__init__.py")) )

    def is_setup_function(fun):
        return inspect.isfunction(fun) and \
            fun.__name__ == "setup" and \
            any(param.annotation == web.Application
                for name, param in inspect.signature(fun).parameters.items())

    subsystems = []
    for path in package_dir.iterdir():
        if is_py_module(path):
            name = path.name.replace(path.suffix, "")
            module = importlib.import_module("." + name, package_dir.name)
            if any(inspect.getmembers(module, is_setup_function)):
                subsystems.append(module)

    return subsystems


def test_schema_sections(app_config_schema, app_subsystems):
    """
    CONVENTION:
        Every section in the config-file (except for 'version' and 'main')
        is named after an application's subsystem
    """
    section_names= [ getattr(module, "CONFIG_SECTION_NAME", module.__name__.split(".")[-1])
                        for module in app_subsystems] + ['version', 'main']

    for section in app_config_schema.keys:
        assert section.name in section_names, "Check application config schema!"
