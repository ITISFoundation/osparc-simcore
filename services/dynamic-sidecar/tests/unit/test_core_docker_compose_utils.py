# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
import yaml
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.async_utils import run_sequentially_in_context
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    docker_compose_config,
    docker_compose_down,
    docker_compose_restart,
    docker_compose_up,
)
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore


@pytest.fixture
def compose_spec(network_name: str) -> dict:
    return {
        "version": "3.8",
        "services": {
            "my-container": {
                "deploy": {
                    "resources": {
                        "limits": {"cpus": 4, "memory": "17179869184"},
                        "reservations": {"cpus": 0.1, "memory": "2147483648"},
                    }
                },
                "environment": [
                    "DY_SIDECAR_PATH_INPUTS=/work/inputs",
                    "DY_SIDECAR_PATH_OUTPUTS=/work/outputs",
                    'DY_SIDECAR_STATE_PATHS=["/work/workspace"]',
                ],
                "working_dir": "/work",
                "image": "busybox",
                "command": 'sleep 3; echo "tschuss"',
                "networks": [
                    network_name,
                ],
            }
        },
        "networks": {
            network_name: {"driver": "overlay", "external": {"name": network_name}}
        },
    }


@pytest.fixture
def compose_spec_yaml(faker: Faker) -> str:
    network_name = f"dy-sidecar_{faker.uuid4()}"
    # return


async def test_it(compose_spec_yaml: str, mock_environment: EnvVarsDict):
    settings = DynamicSidecarSettings.create_from_envs()

    compose_spec = yaml.safe_load(compose_spec_yaml)
    shared_store = SharedStore(
        compose_spec=compose_spec_yaml,
        container_names=list(compose_spec["services"].keys()),
    )
    r = await docker_compose_down(
        shared_store,
        settings,
        10,
    )
    assert r.success, r.decoded_stdout

    assert r.success, r.decoded_stdout
    r = await docker_compose_up(
        shared_store,
        settings,
        10,
    )
    assert r.success, r.decoded_stdout


def test_enforce_sequencial_execution():
    assert run_sequentially_in_context


assert docker_compose_config
assert docker_compose_restart


def test_docker_compose_down_timeouts():
    assert docker_compose_down
    raise NotImplementedError("Add test around timeout error below")
    # 2022-07-05T22:12:57.276979315Z WARNING:simcore_service_dynamic_sidecar.core.utils:
    #   command='docker-compose --project-name dy-sidecar_2f734972-8282-4a26-9904-60a4a82406ee
    #   --file "/tmp/3cr4o_k8" down --volumes --remove-orphans --timeout 5'
    #   timed out after command_timeout=10.0s
