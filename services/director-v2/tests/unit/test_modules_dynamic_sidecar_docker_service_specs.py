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
from simcore_service_director_v2.core.settings import (
    AppSettings,
    DynamicSidecarSettings,
)
from simcore_service_director_v2.models.schemas.dynamic_services import SchedulerData
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs import (
    get_dynamic_sidecar_spec,
)

# FIXTURES


@pytest.fixture
def mocked_env(monkeypatch: MonkeyPatch) -> Iterator[Dict[str, str]]:
    env_vars: Dict[str, str] = {
        "REGISTRY_AUTH": "false",
        "REGISTRY_USER": "test",
        "REGISTRY_PW": "test",
        "REGISTRY_SSL": "false",
        "DYNAMIC_SIDECAR_IMAGE": "local/dynamic-sidecar:MOCK",
        "POSTGRES_HOST": "test_host",
        "POSTGRES_USER": "test_user",
        "POSTGRES_PASSWORD": "test_password",
        "POSTGRES_DB": "test_db",
        "SIMCORE_SERVICES_NETWORK_NAME": "simcore_services_network_name",
        "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
        "SWARM_STACK_NAME": "test_swarm_name",
    }

    with monkeypatch.context() as m:
        for key, value in env_vars.items():
            m.setenv(key, value)

        yield env_vars


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
def test_get_dynamic_proxy_spec(
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    simcore_service_labels: SimcoreServiceLabels,
) -> None:
    dynamic_sidecar_spec = get_dynamic_sidecar_spec(
        scheduler_data=scheduler_data,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        dynamic_sidecar_network_id=dynamic_sidecar_network_id,
        swarm_network_id=swarm_network_id,
        settings=cast(SimcoreServiceSettingsLabel, simcore_service_labels.settings),
        app_settings=AppSettings.create_from_envs(),
    )
    assert dynamic_sidecar_spec
    pprint(dynamic_sidecar_spec)
    # TODO: finish test when working on https://github.com/ITISFoundation/osparc-simcore/issues/2454
