# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import argparse
import importlib
import inspect
import re
import unittest.mock as mock
from pathlib import Path
from typing import Dict, List

import pytest
import yaml
from aiohttp import web

from servicelib.application_setup import is_setup_function
from simcore_service_webserver.application_config import create_schema
from simcore_service_webserver.cli import parse, setup_parser
from simcore_service_webserver.resources import resources
from utils_environs import eval_service_environ, load_env


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
        env_devel = load_env(f)
    return env_devel

@pytest.fixture("session")
def service_webserver_environ(services_docker_compose_file, devel_environ, osparc_simcore_root_dir):
    """ Creates a dict with the environment variables
        inside of a webserver container
    """
    host_environ = devel_environ
    image_environ = {
        'SIMCORE_WEB_OUTDIR': 'home/scu/services/web/client',  # defined in Dockerfile
        'OSPARC_SIMCORE_REPO_ROOTDIR': str(osparc_simcore_root_dir) # defined if pip install --edit (but not in travis!)
    }

    webserver_environ = eval_service_environ(services_docker_compose_file, "webserver",
        host_environ, image_environ, use_env_devel=True)

    return webserver_environ



@pytest.fixture("session")
def app_submodules_with_setup_funs(package_dir) -> List:
    """
        subsystem = all modules in package with a setup function
    """
    def is_py_module(path: Path) -> bool:
        return not path.name.startswith((".", "__")) and \
            ( path.suffix == ".py" or any(path.glob("__init__.py")) )

    modules = []
    for path in package_dir.iterdir():
        if is_py_module(path):
            name = path.name.replace(path.suffix, "")
            module = importlib.import_module("." + name, package_dir.name)
            if module.__name__ != 'simcore_service_webserver.application':
                if any(inspect.getmembers(module, is_setup_function)):
                    modules.append(module)

    assert modules, "Expected subsystem setup modules"
    return modules


@pytest.fixture("session")
def app_subsystems(app_submodules_with_setup_funs) -> List[Dict]:
    metadata = []
    for module in app_submodules_with_setup_funs:
        setup_members = inspect.getmembers(module, is_setup_function)
        if setup_members:
            # finds setup for module
            module_name = module.__name__.replace(".__init__", '')
            setup_fun = None
            for name, fun in setup_members:
                if fun.metadata()['module_name'] == module_name:
                    setup_fun = fun
                    break

            assert setup_fun, f"None of {setup_members} are setup funs for {module_name}"
            metadata.append(setup_fun.metadata())

    return metadata



# TESTS ----------------------------------------------------------------------

@pytest.mark.parametrize("configfile", [str(n)
                                        for n in resources.listdir("config")
                                        ])
def test_correctness_under_environ(configfile, service_webserver_environ):
    parser = setup_parser(argparse.ArgumentParser("test-parser"))

    with mock.patch('os.environ', service_webserver_environ):
        cmd = ["-c", configfile]
        config = parse(cmd, parser)

        for key, value in config.items():
            assert value != 'None', "Use instead Null in {} for {}".format(
                configfile, key)

        # adds some defaults checks here
        assert config['smtp']['username'] is None


def test_setup_per_app_subsystem(app_submodules_with_setup_funs):
    for module in app_submodules_with_setup_funs:
        setup_members = inspect.getmembers(module, is_setup_function)
        if setup_members:
            # finds setup for module
            module_name = module.__name__.replace(".__init__", '')
            setup_fun = None
            for name, fun in setup_members:
                if fun.metadata()['module_name'] == module_name:
                    setup_fun = fun
                    break

            assert setup_fun, f"None of {setup_members} are setup funs for {module_name}"


def test_schema_sections(app_config_schema, app_subsystems):
    """
    CONVENTION:
        Every section in the config-file (except for 'version' and 'main')
        is named after an application's subsystem
    """
    section_names= [ metadata['config_section'] for metadata in app_subsystems] + ['version', 'main']

    for section in app_config_schema.keys:
        assert section.name in section_names, "Check application config schema!"
