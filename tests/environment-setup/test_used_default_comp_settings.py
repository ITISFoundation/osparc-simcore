# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import importlib.util
from pathlib import Path
from typing import Tuple

import pytest


@pytest.mark.parametrize(
    "list_of_envs",
    [
        pytest.param([], id="None"),
        pytest.param([("DEFAULT_MAX_NANO_CPUS", f"{int(10e09)}")], id="set nano cpus"),
        pytest.param([("DEFAULT_MAX_MEMORY", f"{int(1e09)}")], id="set max memory"),
    ],
)
def test_default_max_values_are_same_in_director_and_sidecar(
    osparc_simcore_root_dir: Path, list_of_envs: Tuple[str, str], monkeypatch, request
):

    for env_name, env_value in list_of_envs:
        monkeypatch.setenv(env_name, env_value)

    spec_sidecar = importlib.util.spec_from_file_location(
        f"sidecar_defaults_{request.node.callspec.id}",
        osparc_simcore_root_dir
        / "packages/settings-library/src/settings_library/comp_services.py",
    )
    assert spec_sidecar is not None
    module_sidecar = importlib.util.module_from_spec(spec_sidecar)
    spec_sidecar.loader.exec_module(module_sidecar)  # type: ignore
    sidecar_comp_services = module_sidecar.CompServices()  # type: ignore

    spec_director = importlib.util.spec_from_file_location(
        f"director_defaults_{request.node.callspec.id}",
        osparc_simcore_root_dir
        / "services/director/src/simcore_service_director/config.py",
    )
    assert spec_director is not None
    module_director = importlib.util.module_from_spec(spec_director)
    spec_director.loader.exec_module(module_director)  # type: ignore

    # check the defaults are correct
    assert (
        sidecar_comp_services.DEFAULT_MAX_MEMORY == module_director.DEFAULT_MAX_MEMORY  # type: ignore
    )
    assert (
        sidecar_comp_services.DEFAULT_MAX_NANO_CPUS
        == module_director.DEFAULT_MAX_NANO_CPUS  # type: ignore
    )
