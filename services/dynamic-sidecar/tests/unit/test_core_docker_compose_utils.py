# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-function-args

import asyncio
from typing import Any

import pytest
import yaml
from faker import Faker
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    docker_compose_config,
    docker_compose_create,
    docker_compose_down,
    docker_compose_pull,
    docker_compose_restart,
    docker_compose_rm,
    docker_compose_start,
)
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.core.utils import CommandResult

SLEEP_TIME_S = 60
COMPOSE_SPEC_SAMPLE = {
    "version": "3.8",
    "services": {
        "my-test-container": {
            "environment": [
                "DY_SIDECAR_PATH_INPUTS=/work/inputs",
                "DY_SIDECAR_PATH_OUTPUTS=/work/outputs",
                'DY_SIDECAR_STATE_PATHS=["/work/workspace"]',
            ],
            "working_dir": "/work",
            "image": "busybox:latest",
            "command": f"sh -c \"echo 'setup {__name__}'; sleep {SLEEP_TIME_S}; echo 'teardown {__name__}'\"",
        }
    },
}


@pytest.fixture
def compose_spec_yaml(faker: Faker) -> str:
    return yaml.safe_dump(COMPOSE_SPEC_SAMPLE, indent=1)


@pytest.mark.parametrize("with_restart", [True, False])
async def test_docker_compose_workflow(
    compose_spec_yaml: str,
    mock_environment: EnvVarsDict,
    with_restart: bool,
    ensure_run_in_sequence_context_is_empty: None,
    mocker: MockerFixture,
):
    settings = ApplicationSettings.create_from_envs()

    def _print_result(r: CommandResult):
        assert r.elapsed
        assert r.elapsed > 0
        print(f"{r.command:*^100}", "\nELAPSED:", r.elapsed)

    compose_spec: dict[str, Any] = yaml.safe_load(compose_spec_yaml)
    print("compose_spec:\n", compose_spec)

    # validates specs
    r = await docker_compose_config(compose_spec_yaml, timeout=10)
    _print_result(r)
    assert r.success, r.message

    # removes all stopped containers from specs
    r = await docker_compose_rm(compose_spec_yaml, settings)
    _print_result(r)
    assert r.success, r.message

    # pulls containers before starting them
    fake_app = mocker.AsyncMock()
    fake_app.state.settings = settings
    await docker_compose_pull(fake_app, compose_spec_yaml)

    # creates containers
    r = await docker_compose_create(compose_spec_yaml, settings)
    _print_result(r)
    assert r.success, r.message

    # tries to start containers which were not able to start
    r = await docker_compose_start(compose_spec_yaml, settings)
    _print_result(r)
    assert r.success, r.message

    if with_restart:
        # restarts
        r = await docker_compose_restart(compose_spec_yaml, settings)
        _print_result(r)
        assert r.success, r.message

    # stops and removes
    r = await docker_compose_down(compose_spec_yaml, settings)

    _print_result(r)
    assert r.success, r.message

    # full cleanup
    r = await docker_compose_rm(compose_spec_yaml, settings)

    _print_result(r)
    assert r.success, r.message


async def test_burst_calls_to_docker_compose_config(
    compose_spec_yaml: str,
    mock_environment: EnvVarsDict,
    ensure_run_in_sequence_context_is_empty: None,
):
    CALLS_COUNT = 10  # tried manually with 1E3 but takes too long
    results = await asyncio.gather(
        *(
            docker_compose_config(
                compose_spec_yaml,
                timeout=100 + i,  # large timeout and emulates change in parameters
            )
            for i in range(CALLS_COUNT)
        ),
        return_exceptions=True,
    )

    exceptions = [r for r in results if isinstance(r, Exception)]
    assert not exceptions, "docker_compose* does NOT raise exceptions"

    assert all(
        isinstance(r, CommandResult) for r in results
    ), "docker_compose* does NOT raise exceptions"

    success = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    assert len(success) == CALLS_COUNT
    assert not failed


async def test_docker_start_fails_if_containers_are_not_present(
    compose_spec_yaml: str,
    mock_environment: EnvVarsDict,
    ensure_run_in_sequence_context_is_empty: None,
):
    settings = ApplicationSettings.create_from_envs()

    def _print_result(r: CommandResult):
        assert r.elapsed
        assert r.elapsed > 0
        print(f"{r.command:*^100}", "\nELAPSED:", r.elapsed)

    compose_spec: dict[str, Any] = yaml.safe_load(compose_spec_yaml)
    print("compose_spec:\n", compose_spec)

    # validates specs
    r = await docker_compose_config(compose_spec_yaml, timeout=10)
    _print_result(r)
    assert r.success, r.message

    # fails when containers are missing
    r = await docker_compose_start(compose_spec_yaml, settings)
    _print_result(r)
    assert r.success is False, r.message
