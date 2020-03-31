# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import argparse
import importlib
import inspect
import unittest.mock as mock
from pathlib import Path
from typing import Dict, List

import pytest

from pytest_simcore.helpers.utils_environs import eval_service_environ, load_env
from servicelib.application_setup import is_setup_function
from simcore_service_webserver.application_config import create_schema
from simcore_service_webserver.cli import parse, setup_parser
from simcore_service_webserver.login import APP_CONFIG_KEY
from simcore_service_webserver.login import CONFIG_SECTION_NAME as LOGIN_SECTION
from simcore_service_webserver.login import (
    DB_SECTION,
    SMTP_SECTION,
    _create_login_config,
)
from simcore_service_webserver.login.cfg import DEFAULTS as CONFIG_DEFAULTS
from simcore_service_webserver.login.cfg import Cfg
from simcore_service_webserver.resources import resources

config_yaml_filenames = [str(name) for name in resources.listdir("config")]


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
def service_webserver_environ(
    services_docker_compose_file, devel_environ, osparc_simcore_root_dir
):
    """ Creates a dict with the environment variables
        inside of a webserver container
    """
    host_environ = devel_environ
    image_environ = {
        "SIMCORE_WEB_OUTDIR": "home/scu/services/web/client",  # defined in Dockerfile
        "OSPARC_SIMCORE_REPO_ROOTDIR": str(
            osparc_simcore_root_dir
        ),  # defined if pip install --edit (but not in travis!)
    }

    webserver_environ = eval_service_environ(
        services_docker_compose_file,
        "webserver",
        host_environ,
        image_environ,
        use_env_devel=True,
    )

    return webserver_environ


@pytest.fixture("session")
def app_submodules_with_setup_funs(package_dir) -> List:
    """
        subsystem = all modules in package with a setup function
    """

    def is_py_module(path: Path) -> bool:
        return not path.name.startswith((".", "__")) and (
            path.suffix == ".py" or any(path.glob("__init__.py"))
        )

    modules = []
    for path in package_dir.iterdir():
        if is_py_module(path):
            name = path.name.replace(path.suffix, "")
            module = importlib.import_module("." + name, package_dir.name)
            if module.__name__ != "simcore_service_webserver.application":
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
            module_name = module.__name__.replace(".__init__", "")
            setup_fun = None
            for name, fun in setup_members:
                if fun.metadata()["module_name"] == module_name:
                    setup_fun = fun
                    break

            assert (
                setup_fun
            ), f"None of {setup_members} are setup funs for {module_name}"
            metadata.append(setup_fun.metadata())

    return metadata


# TESTS ----------------------------------------------------------------------


@pytest.mark.parametrize("configfile", config_yaml_filenames)
def test_correctness_under_environ(configfile, service_webserver_environ):
    parser = setup_parser(argparse.ArgumentParser("test-parser"))

    with mock.patch("os.environ", service_webserver_environ):
        cmd = ["-c", configfile]
        config = parse(cmd, parser)

        for key, value in config.items():
            assert value != "None", "Use instead Null in {} for {}".format(
                configfile, key
            )

        # adds some defaults checks here


def test_setup_per_app_subsystem(app_submodules_with_setup_funs):
    for module in app_submodules_with_setup_funs:
        setup_members = inspect.getmembers(module, is_setup_function)
        if setup_members:
            # finds setup for module
            module_name = module.__name__.replace(".__init__", "")
            setup_fun = None
            for name, fun in setup_members:
                if fun.metadata()["module_name"] == module_name:
                    setup_fun = fun
                    break

            assert (
                setup_fun
            ), f"None of {setup_members} are setup funs for {module_name}"


def test_schema_sections(app_config_schema, app_subsystems):
    """
    CONVENTION:
        Every section in the config-file (except for 'version' and 'main')
        is named after an application's subsystem
    """
    section_names = [metadata["config_section"] for metadata in app_subsystems] + [
        "version",
        "main",
    ]

    for section in app_config_schema.keys:
        assert section.name in section_names, "Check application config schema!"


@pytest.mark.parametrize("configfile", config_yaml_filenames)
def test_creation_of_login_config(configfile, service_webserver_environ):
    parser = setup_parser(argparse.ArgumentParser("test-parser"))

    with mock.patch("os.environ", service_webserver_environ):
        app_config = parse(["-c", configfile], parser)

        for key, value in app_config.items():
            assert value != "None", "Use instead Null in {} for {}".format(
                configfile, key
            )

        # sections of app config used
        assert LOGIN_SECTION in app_config.keys()
        assert SMTP_SECTION in app_config.keys()
        assert DB_SECTION in app_config.keys()

        # creates update config
        fake_app = {APP_CONFIG_KEY: app_config}
        fake_storage = object()

        update_cfg = _create_login_config(fake_app, fake_storage)
        assert all(
            value.lower() is not ["none", "null", ""]
            for value in update_cfg.values()
            if isinstance(value, str)
        )

        # creates login.cfg
        login_internal_cfg = Cfg(CONFIG_DEFAULTS)
        try:
            login_internal_cfg.configure(update_cfg)
        except ValueError as ee:
            pytest.fail(f"{ee}: \n {update_cfg}")



@pytest.mark.parametrize("configfile", config_yaml_filenames)
def test_resource_manager_config_section(configfile, service_webserver_environ):
    parser = setup_parser(argparse.ArgumentParser("test-parser"))

    with mock.patch("os.environ", service_webserver_environ):
        app_config = parse(["-c", configfile], parser)

        # NOTE: during PR #1401 some tests starting failing because these
        # config entries were returning the wrong type.
        # I would expect traferet to auto-cast.
        # Let's check against multiple configs
        #
        # >>> import trafaret as t
        # >>> t.Int().check(3)
        # 3
        # >>> t.Int().check("3")
        # '3'
        # >>> t.ToInt().check("3")
        # 3
        # >>> t.ToInt().check(3)
        # 3
        #
        # NOTE: Changelog 2.0.2 https://trafaret.readthedocs.io/en/latest/changelog.html
        #   construct for int and float will use ToInt and ToFloat
        #
        # RESOLVED: changing the schema from Int() -> ToInt()
        assert isinstance(app_config["resource_manager"]["enabled"], bool)

        # Checks implementations of .resource_manager.config.get_* helpers
        assert isinstance(app_config["resource_manager"]["resource_deletion_timeout_seconds"], int)
        assert isinstance(app_config["resource_manager"]["garbage_collection_interval_seconds"], int)


       