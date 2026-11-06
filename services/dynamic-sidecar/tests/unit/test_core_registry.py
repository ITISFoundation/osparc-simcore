# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path

import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_registry import RegistrySettings
from simcore_service_dynamic_sidecar.core.registry import (
    DOCKER_CONFIG_JSON_PATH,
    _login_registry,
    _RegistryNotReachableError,
)
from simcore_service_dynamic_sidecar.core.utils import CommandResult


def _get_registry_config(
    *,
    url: str = "localhost:1111",
    auth: str = "true",
    user: str = "user",
    password: str = "password",  # noqa: S107
    ssl: str = "false",
) -> str:
    return json.dumps(
        {
            "REGISTRY_URL": url,
            "REGISTRY_AUTH": auth,
            "REGISTRY_USER": user,
            "REGISTRY_PW": password,
            "REGISTRY_SSL": ssl,
        }
    )


@pytest.fixture
def backup_docker_config_file() -> Iterable[None]:
    backup_path = DOCKER_CONFIG_JSON_PATH.parent / f"{DOCKER_CONFIG_JSON_PATH.name}.backup"

    if not backup_path.exists() and DOCKER_CONFIG_JSON_PATH.exists():
        backup_path.write_text(DOCKER_CONFIG_JSON_PATH.read_text())

    if DOCKER_CONFIG_JSON_PATH.exists():
        DOCKER_CONFIG_JSON_PATH.unlink()

    yield

    if backup_path.exists():
        DOCKER_CONFIG_JSON_PATH.write_text(backup_path.read_text())
        backup_path.unlink()


@pytest.fixture
def unset_registry_envs(mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch) -> None:
    for env in (
        "REGISTRY_AUTH",
        "REGISTRY_PATH",
        "REGISTRY_URL",
        "REGISTRY_USER",
        "REGISTRY_PW",
        "REGISTRY_SSL",
    ):
        monkeypatch.delenv(env, raising=False)


@pytest.fixture
def mock_registry_settings_with_auth(
    unset_registry_envs: None,
    backup_docker_config_file: None,
    monkeypatch: pytest.MonkeyPatch,
    docker_registry: str,
) -> None:
    monkeypatch.setenv(
        "DY_DEPLOYMENT_REGISTRY_SETTINGS",
        _get_registry_config(
            url=docker_registry,
            user="testuser",
            password="testpassword",  # noqa: S106
        ),
    )


@pytest.mark.docker_exclusive(
    reason="rewrites the machine-global ~/.docker/config.json and uses the shared fixed-name/port "
    "`docker_registry` container",
)
async def test__login_registry(
    mock_registry_settings_with_auth: None,
    app: FastAPI,
    docker_registry: str,
) -> None:
    registry_settings: RegistrySettings = app.state.settings.DY_DEPLOYMENT_REGISTRY_SETTINGS
    assert registry_settings.REGISTRY_URL == docker_registry  # noqa: SIM300
    assert registry_settings.REGISTRY_AUTH is True
    assert registry_settings.REGISTRY_USER == "testuser"
    assert registry_settings.REGISTRY_PW.get_secret_value() == "testpassword"
    assert registry_settings.REGISTRY_SSL is False

    await _login_registry(registry_settings)

    config_json = json.loads(DOCKER_CONFIG_JSON_PATH.read_text())
    assert len(config_json["auths"]) == 1
    assert registry_settings.REGISTRY_URL in config_json["auths"]


def _create_registry_settings(password: str) -> RegistrySettings:
    return RegistrySettings(
        REGISTRY_AUTH=True,
        REGISTRY_URL="localhost:1111",
        REGISTRY_USER="testuser",
        REGISTRY_PW=SecretStr(password),
        REGISTRY_SSL=False,
    )


@pytest.mark.parametrize(
    "response_message",
    [
        "Error response from daemon: unauthorized: authentication required",
        "Execution timed out after 5 secs",
    ],
)
async def test__login_registry_does_not_leak_password_when_login_fails(
    mocker: MockerFixture,
    caplog: pytest.LogCaptureFixture,
    response_message: str,
):
    password = "s3cr3t-with-a-quote'-inside"  # noqa: S105
    caplog.set_level(logging.DEBUG)

    async def _finish_with_failure(command: str, **kwargs: object) -> CommandResult:
        assert kwargs.get("pipe_as_input") == f"{password}\n"
        return CommandResult(success=False, message=response_message, command=command, elapsed=5.0)

    mocked_async_command = mocker.patch(
        "simcore_service_dynamic_sidecar.core.registry.async_command",
        side_effect=_finish_with_failure,
    )

    with pytest.raises(_RegistryNotReachableError) as exc_info:
        await _login_registry(_create_registry_settings(password))

    assert mocked_async_command.await_args is not None
    executed_command: str = mocked_async_command.await_args.args[0]
    assert password not in executed_command
    assert password not in caplog.text
    assert password not in f"{exc_info.value}"


async def test__login_registry_passes_password_to_docker_on_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """Runs against a fake `docker` executable that dumps what it receives"""
    password = "s3cr3t-with-a-quote'-inside"  # noqa: S105

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    argv_file = tmp_path / "argv.txt"
    stdin_file = tmp_path / "stdin.txt"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'printf "%s\\n" "$*" > "$FAKE_DOCKER_ARGV"',
                'cat > "$FAKE_DOCKER_STDIN"',
                'echo "Login Succeeded"',
                "",
            ]
        )
    )
    fake_docker.chmod(0o755)

    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_DOCKER_ARGV", f"{argv_file}")
    monkeypatch.setenv("FAKE_DOCKER_STDIN", f"{stdin_file}")
    caplog.set_level(logging.DEBUG)

    await _login_registry(_create_registry_settings(password))

    assert stdin_file.read_text() == f"{password}\n"
    received_argv = argv_file.read_text()
    assert "--password-stdin" in received_argv
    assert password not in received_argv
    assert password not in caplog.text
