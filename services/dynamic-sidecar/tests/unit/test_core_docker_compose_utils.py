# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml
from faker import Faker
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.async_utils import run_sequentially_in_context
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    docker_compose_config,
    docker_compose_down,
    docker_compose_restart,
    docker_compose_rm,
    docker_compose_up,
)
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings

COMPOSE_SPEC_SAMPLE = {
    "version": "3.8",
    "services": {
        "my-container": {
            "environment": [
                "DY_SIDECAR_PATH_INPUTS=/work/inputs",
                "DY_SIDECAR_PATH_OUTPUTS=/work/outputs",
                'DY_SIDECAR_STATE_PATHS=["/work/workspace"]',
            ],
            "working_dir": "/work",
            "image": "busybox",
            "command": "sh -c \"echo 'setup'; sleep 60; echo 'teardown'\"",
        }
    },
}


@pytest.fixture
def compose_spec_yaml(faker: Faker) -> str:
    return yaml.safe_dump(COMPOSE_SPEC_SAMPLE, indent=1)


# async def test_docker_compose_workflow(
async def test_it(compose_spec_yaml: str, mock_environment: EnvVarsDict):
    settings = DynamicSidecarSettings.create_from_envs()

    compose_spec: dict[str, Any] = yaml.safe_load(compose_spec_yaml)
    print(compose_spec)

    # validates specs
    r = await docker_compose_config(
        compose_spec_yaml,
        settings,
        10,
    )
    print(r.message, "ELAPSED:", r.elapsed)
    assert r.success, r.message

    # removes all stopped containers from specs
    r = await docker_compose_rm(
        compose_spec_yaml,
        settings,
    )
    print(r.message, "ELAPSED:", r.elapsed)
    assert r.success, r.message

    # creates and starts in detached mode
    r = await docker_compose_up(
        compose_spec_yaml,
        settings,
        10,
    )
    print(r.message, "ELAPSED:", r.elapsed)
    assert r.success, r.message

    # stops and removes
    # TODO: test if --remove-orphans might affect containers from other Compose
    # NOTE: tried using CMD and does not seem to affect. Which orphans are those? previously not downed because timeout?
    r = await docker_compose_down(
        compose_spec_yaml,
        settings,
        10,
    )

    print(r.message, "ELAPSED:", r.elapsed)
    assert r.success, r.message

    # full cleanup
    r = await docker_compose_rm(
        compose_spec_yaml,
        settings,
    )

    print(r.message, "ELAPSED:", r.elapsed)
    assert r.success, r.message


@pytest.mark.skip(reason="DEV")
def test_enforce_sequencial_execution():
    assert run_sequentially_in_context
    assert docker_compose_config
    assert docker_compose_restart


@pytest.mark.skip(reason="DEV")
def test_docker_compose_down_timeouts():
    assert docker_compose_down
    raise NotImplementedError("Add test around timeout error below")
    # 2022-07-05T22:12:57.276979315Z WARNING:simcore_service_dynamic_sidecar.core.utils:
    #   command='docker-compose --project-name dy-sidecar_2f734972-8282-4a26-9904-60a4a82406ee
    #   --file "/tmp/3cr4o_k8" down --volumes --remove-orphans --timeout 5'
    #   timed out after command_timeout=10.0s


@pytest.mark.skip(reason="DEV")
async def test_docker_compose_calls_bursts(
    tmp_path: Path, mock_environment: EnvVarsDict, compose_spec_yaml: str
):
    settings = DynamicSidecarSettings.create_from_envs()

    r = await docker_compose_config(compose_spec_yaml, settings, 1000)

    results = await asyncio.gather(
        *(docker_compose_config(compose_spec_yaml, settings, 1000) for _ in range(100)),
        return_exceptions=True
    )
    for r in results:
        print(r)

    assert all(not isinstance(r, Exception) and r.success for r in results)
