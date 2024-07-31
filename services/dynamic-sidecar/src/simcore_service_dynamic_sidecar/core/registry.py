import logging
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from settings_library.docker_registry import RegistrySettings

from ..modules.service_liveness import wait_for_service_liveness
from .settings import ApplicationSettings
from .utils import CommandResult, async_command

_logger = logging.getLogger(__name__)

DOCKER_CONFIG_JSON_PATH: Final[Path] = Path.home() / ".docker" / "config.json"


class _RegistryNotReachableError(Exception):
    pass


def _get_registry_url(registry_settings: RegistrySettings) -> str:
    protocol = "https" if registry_settings.REGISTRY_SSL else "http"
    return f"{protocol}://{registry_settings.resolved_registry_url}/"


async def _login_registry(registry_settings: RegistrySettings) -> None:
    command_result: CommandResult = await async_command(
        (
            f"echo '{registry_settings.REGISTRY_PW.get_secret_value()}' | "
            f"docker login {registry_settings.api_url} "
            f"--username '{registry_settings.REGISTRY_USER}' "
            "--password-stdin"
        ),
        timeout=5,
    )
    if "Login Succeeded" not in command_result.message:
        _logger.error("Response: %s", command_result)
        error_message = f"Could not contact registry with the following credentials {registry_settings}"
        raise _RegistryNotReachableError(error_message)

    _logger.debug("Logged into registry: %s", registry_settings)


async def wait_for_registries_liveness(app: FastAPI) -> None:
    # NOTE: also logins to the registries when the health check is enforced
    settings: ApplicationSettings = app.state.settings

    await wait_for_service_liveness(
        _login_registry,
        service_name="Internal Registry",
        endpoint=_get_registry_url(settings.DY_DEPLOYMENT_REGISTRY_SETTINGS),
        registry_settings=settings.DY_DEPLOYMENT_REGISTRY_SETTINGS,
    )

    if settings.DY_DOCKER_HUB_REGISTRY_SETTINGS:
        await wait_for_service_liveness(
            _login_registry,
            service_name="DockerHub Registry",
            endpoint=_get_registry_url(settings.DY_DOCKER_HUB_REGISTRY_SETTINGS),
            registry_settings=settings.DY_DOCKER_HUB_REGISTRY_SETTINGS,
        )
