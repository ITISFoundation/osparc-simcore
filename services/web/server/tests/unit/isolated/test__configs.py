# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


# NOTE: This test will fail with protobuf>=5.29.4
#
# E     TypeError: Descriptors cannot be created directly.
# E     If this call came from a _pb2.py file, your generated code is out of date and must be regenerated with protoc >= 3.19.0.
# E     If you cannot immediately regenerate your protos, some other possible workarounds are:
# E      1. Downgrade the protobuf package to 3.20.x or lower.
# E      2. Set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python (but this will use pure-Python parsing and will be much slower).
# E
# E     More information: https://developers.google.com/protocol-buffers/docs/news/2022-05-06#python-updates
#
# SEE requirements/constraints.txt


import importlib
import inspect
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pytest_simcore.helpers.deprecated_environs import eval_service_environ
from servicelib.aiohttp.application_setup import is_setup_function


@pytest.fixture(scope="session")
def app_config_schema():
    msg = "DEPRECATED. MUST NOT BE USED"
    raise RuntimeError(msg)


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

    return eval_service_environ(
        services_docker_compose_file,
        "webserver",
        host_environ,
        image_environ,
        use_env_devel=True,
    )


@pytest.fixture(scope="session")
def app_submodules_with_setup_funs(package_dir: Path) -> set[ModuleType]:
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
            if module.__name__ != "simcore_service_webserver.application" and any(
                inspect.getmembers(module, is_setup_function)
            ):
                modules.add(module)

    assert modules, "Expected subsystem setup modules"
    return modules


@pytest.fixture(scope="session")
def app_modules_metadata(
    app_submodules_with_setup_funs: set[ModuleType],
) -> list[dict[str, Any]]:
    NameFuncPair = tuple[str, Callable]

    register: set[str] = set()
    setup_funcs_metadata: list[dict[str, Any]] = []

    for module in app_submodules_with_setup_funs:
        # SEE packages/service-library/src/servicelib/aiohttp/application_setup.py
        setup_members: list[NameFuncPair] = inspect.getmembers(
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


def test_setup_per_app_subsystem(app_submodules_with_setup_funs):
    for module in app_submodules_with_setup_funs:
        setup_members = inspect.getmembers(module, is_setup_function)
        assert (
            setup_members
        ), f"None of {setup_members} are setup funs for {module.__name__}"


@pytest.mark.skip(reason="DEPRECATED")
def test_schema_sections(app_config_schema, app_modules_metadata: list[dict]):
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
