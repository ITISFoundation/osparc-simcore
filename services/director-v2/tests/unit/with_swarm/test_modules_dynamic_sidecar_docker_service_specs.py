# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from pprint import pprint
from typing import Dict, Iterator, cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from models_library.service_settings_labels import (
    SimcoreServiceLabels,
    SimcoreServiceSettingsLabel,
)
from pytest_lazyfixture import lazy_fixture
from settings_library.docker_registry import RegistrySettings
from simcore_service_director_v2.core.settings import DynamicSidecarSettings
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs import (
    get_dynamic_sidecar_spec,
)

# FIXTURES


@pytest.fixture
def mocked_env(monkeypatch: MonkeyPatch) -> Iterator[Dict[str, str]]:
    env_vars: Dict[str, str] = {
        "DYNAMIC_SIDECAR_IMAGE": "local/dynamic-sidecar:MOCK",
    }

    with monkeypatch.context() as m:
        for key, value in env_vars.items():
            m.setenv(key, value)

        yield env_vars


@pytest.fixture
def docker_registry_settings(mocked_end: Dict[str, str]) -> RegistrySettings:
    return RegistrySettings.create_from_envs()


@pytest.fixture
def dynamic_sidecar_settings(mocked_env: Dict[str, str]) -> DynamicSidecarSettings:
    return DynamicSidecarSettings.create_from_envs()


@pytest.fixture
def dynamic_sidecar_network_id() -> str:
    return "mocked_dynamic_sidecar_network_id"


@pytest.fixture
def swarm_network_id() -> str:
    return "mocked_swarm_network_id"


@pytest.fixture
def simcore_service_labels() -> SimcoreServiceLabels:
    # overwrites global fixture
    return SimcoreServiceLabels(
        **SimcoreServiceLabels.Config.schema_extra["examples"][2]
    )


# TESTS


@pytest.mark.parametrize(
    "scheduler_data",
    (
        lazy_fixture("scheduler_data_from_http_request"),
        lazy_fixture("scheduler_data_from_service_labels_stored_data"),
    ),
)
async def test_get_dynamic_proxy_spec(
    scheduler_data: SchedulerData,
    docker_registry_settings: RegistrySettings,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
) -> None:
    dynamic_sidecar_spec = await get_dynamic_sidecar_spec(
        scheduler_data=scheduler_data,
        docker_registry_settings=docker_registry_settings,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
    )
    assert dynamic_sidecar_spec
    pprint(dynamic_sidecar_spec)
    # TODO: finish test when working on https://github.com/ITISFoundation/osparc-simcore/issues/2454
