# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import argparse
import importlib
import inspect
import unittest.mock as mock
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Set, Tuple

import pytest
from pytest_simcore.helpers.utils_environs import eval_service_environ
from servicelib.aiohttp.application_setup import is_setup_function
from simcore_service_webserver._resources import resources

config_yaml_filenames = [str(name) for name in resources.listdir("config")]


@pytest.fixture(scope="session")
def app_config_schema():
    raise RuntimeError("DEPRECATED. MUST NOT BE USED")


@pytest.fixture(scope="session")
def service_webserver_environ(
    services_docker_compose_file, env_devel_dict, osparc_simcore_root_dir
):
    """Creates a dict with the environment variables
    inside of a webserver container
    """
    host_environ = env_devel_dict.copy()
    image_environ = {
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


@pytest.fixture(scope="session")
def app_submodules_with_setup_funs(package_dir: Path) -> Set[ModuleType]:
    """
    subsystem = all modules in package with a setup function
    """

    EXCLUDE = ("data", "templates")

    def validate(path: Path) -> bool:
        return not path.name.startswith((".", "__")) and (
            all(name not in str(path) for name in EXCLUDE)
        )

    modules = set()
    for path in package_dir.rglob("*.py"):
        if validate(path):
            name = ".".join(path.relative_to(package_dir).parts).replace(".py", "")
            module = importlib.import_module("." + name, package_dir.name)
            # NOTE: application import ALL
            if module.__name__ != "simcore_service_webserver.application":
                if "director" in name:
                    print(name)
                if any(inspect.getmembers(module, is_setup_function)):
                    modules.add(module)

    assert modules, "Expected subsystem setup modules"
    return modules


@pytest.fixture(scope="session")
def app_modules_metadata(
    app_submodules_with_setup_funs: Set[ModuleType],
) -> List[Dict[str, Any]]:
    NameFuncPair = Tuple[str, Callable]

    register: Set[str] = set()
    setup_funcs_metadata: List[Dict[str, Any]] = []

    for module in app_submodules_with_setup_funs:
        # SEE packages/service-library/src/servicelib/aiohttp/application_setup.py
        setup_members: List[NameFuncPair] = inspect.getmembers(
            module, is_setup_function
        )
        assert (
            setup_members
        ), f"None of {[s[0] for s in setup_members]} found in {module.__name__} are valid setup functions for"

        assert len(setup_members), "One setup per module"

        for setup_fun_name, setup_fun in setup_members:
            metadata = setup_fun.metadata()
            print(f"{setup_fun_name=} -> {metadata=}")
            # NOTE: same setup_fun can always be imported from the original module
            # therefore there are some cases in which more than one setup_func is
            # present. Here we make sure we do not duplicate them
            if setup_fun_name not in register:
                setup_funcs_metadata.append(metadata)
            register.add(setup_fun_name)

    assert len(app_submodules_with_setup_funs) == len(
        setup_funcs_metadata
    ), "One setup func per module setup"

    return list(setup_funcs_metadata)


# TESTS ----------------------------------------------------------------------


def test_setup_per_app_subsystem(app_submodules_with_setup_funs):
    for module in app_submodules_with_setup_funs:
        setup_members = inspect.getmembers(module, is_setup_function)
        assert (
            setup_members
        ), f"None of {setup_members} are setup funs for {module.__name__}"


@pytest.mark.skip(reason="DEPRECATED")
def test_schema_sections(app_config_schema, app_modules_metadata: List[Dict]):
    """
    CONVENTION:
        Every section in the config-file (except for 'version' and 'main')
        is named after an application's subsystem
    """
    expected_sections = [
        metadata["config_section"] for metadata in app_modules_metadata
    ] + [
        "version",
        "main",
    ]
    assert sorted(expected_sections) == sorted(set(expected_sections)), "no repetitions"

    sections_in_schema = [section.name for section in app_config_schema.keys]

    assert sorted(sections_in_schema) == sorted(expected_sections)


@pytest.mark.skip(reason="DEPRECATED")
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
        assert isinstance(
            app_config["resource_manager"]["resource_deletion_timeout_seconds"], int
        )
        assert isinstance(
            app_config["resource_manager"]["garbage_collection_interval_seconds"], int
        )
