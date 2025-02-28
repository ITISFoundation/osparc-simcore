# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import pytest
import yaml
from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.containers import DcokerComposeYamlStr
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import containers
from settings_library.redis import RedisSettings
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.models.shared_store import (
    SharedStore,
    get_shared_store,
)

pytest_simcore_core_services_selection = [
    "redis",
    "rabbit",
]


@pytest.fixture
def mock_environment(
    redis_service: RedisSettings, mock_environment: EnvVarsDict
) -> EnvVarsDict:
    return mock_environment


@pytest.fixture
def dynamic_sidecar_network_name() -> str:
    return "entrypoint_container_network"


@pytest.fixture
def docker_compose_yaml(dynamic_sidecar_network_name: str) -> DcokerComposeYamlStr:
    return yaml.dump(
        {
            "version": "3",
            "services": {
                "first-box": {
                    "image": "busybox:latest",
                    "networks": {
                        dynamic_sidecar_network_name: None,
                    },
                    "labels": {"io.osparc.test-label": "mark-entrypoint"},
                },
                "second-box": {"image": "busybox:latest"},
                "egress": {
                    "image": "busybox:latest",
                    "networks": {
                        dynamic_sidecar_network_name: None,
                    },
                },
            },
            "networks": {dynamic_sidecar_network_name: None},
        }
    )


async def test_store_compose_spec(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    docker_compose_yaml: DcokerComposeYamlStr,
    ensure_external_volumes: None,
):
    settings: ApplicationSettings = app.state.settings

    result = await containers.store_compose_spec(
        rpc_client,
        node_id=settings.DY_SIDECAR_NODE_ID,
        docker_compose_yaml=docker_compose_yaml,
    )
    assert result is None

    shared_store: SharedStore = get_shared_store(app)
    assert shared_store.compose_spec is not None
