import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any, Final

import httpx
from fastapi import FastAPI
from settings_library.docker_registry import RegistrySettings
from starlette import status

from ..modules.service_liveness import wait_for_service_liveness
from .settings import ApplicationSettings

_logger = logging.getLogger(__name__)

DOCKER_CONFIG_JSON_PATH: Final[Path] = Path.home() / ".docker" / "config.json"


class _RegistryNotReachableError(Exception):
    pass


def _get_registry_url(registry_settings: RegistrySettings) -> str:
    protocol = "https" if registry_settings.REGISTRY_SSL else "http"
    return f"{protocol}://{registry_settings.api_url}/"


async def _is_registry_reachable(registry_settings: RegistrySettings) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        params = {}
        if registry_settings.REGISTRY_AUTH:
            params["auth"] = (
                registry_settings.REGISTRY_USER,
                registry_settings.REGISTRY_PW.get_secret_value(),
            )

        url = _get_registry_url(registry_settings)

        _logger.info("Registry test url ='%s'", url)
        response = await client.get(url, **params)
        reachable = response.status_code == status.HTTP_200_OK and response.json() == {}
        if not reachable:
            _logger.error("Response: %s", response)
            error_message = (
                f"Could not reach registry {registry_settings.api_url} "
                f"auth={registry_settings.REGISTRY_AUTH}"
            )
            raise _RegistryNotReachableError(error_message)


async def _is_dockerhub_reachable(registry_settings: RegistrySettings) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        params: dict[str, Any] = {"headers": {"Content-Type": "application/json"}}
        if registry_settings.REGISTRY_AUTH:
            params["auth"] = (
                registry_settings.REGISTRY_USER,
                registry_settings.REGISTRY_PW.get_secret_value(),
            )
            params["data"] = json.dumps(
                {
                    "username": registry_settings.REGISTRY_USER,
                    "password": registry_settings.REGISTRY_PW.get_secret_value(),
                }
            )

        # NOTE: uses different URL than the one specified in the configuration
        url = "https://hub.docker.com/v2/users/login"

        _logger.info("Registry test url ='%s'", url)
        response = await client.post(url, **params)
        reachable = (
            response.status_code == status.HTTP_200_OK and "token" in response.json()
        )
        if not reachable:
            _logger.error("Response: %s %s", response, response.text)
            error_message = (
                f"Could not reach registry {response.request.url}"
                f"auth={registry_settings.REGISTRY_AUTH}, because: {response.text}"
            )
            raise _RegistryNotReachableError(error_message)


async def wait_for_registries_liveness(app: FastAPI) -> None:
    settings: ApplicationSettings = app.state.settings

    await wait_for_service_liveness(
        _is_registry_reachable,
        service_name="Internal Registry",
        endpoint=_get_registry_url(settings.DY_DEPLOYMENT_REGISTRY_SETTINGS),
        registry_settings=settings.DY_DEPLOYMENT_REGISTRY_SETTINGS,
    )

    if settings.DY_DOCKER_HUB_REGISTRY_SETTINGS:
        await wait_for_service_liveness(
            _is_dockerhub_reachable,
            service_name="DockerHub Registry",
            endpoint="https://hub.docker.com/v2/users/login",
            registry_settings=settings.DY_DOCKER_HUB_REGISTRY_SETTINGS,
        )


async def _login_registries(settings: ApplicationSettings) -> None:
    """
    Creates ~/.docker/config.json and adds docker registry credentials
    """

    def _get_credentials(registry_settings: RegistrySettings) -> str:
        user = registry_settings.REGISTRY_USER
        password = registry_settings.REGISTRY_PW.get_secret_value()
        return base64.b64encode(f"{user}:{password}".encode()).decode()

    def create_docker_config_file(registries_settings: list[RegistrySettings]) -> None:
        docker_config = {
            "auths": {
                f"{settings.resolved_registry_url}": {
                    "auth": _get_credentials(settings)
                }
                for settings in registries_settings
            }
        }

        DOCKER_CONFIG_JSON_PATH.parent.mkdir(exist_ok=True, parents=True)
        DOCKER_CONFIG_JSON_PATH.write_text(json.dumps(docker_config))

    registries_settings: list[RegistrySettings] = []
    if settings.DY_DEPLOYMENT_REGISTRY_SETTINGS.REGISTRY_AUTH:
        registries_settings.append(settings.DY_DEPLOYMENT_REGISTRY_SETTINGS)
    if settings.DY_DOCKER_HUB_REGISTRY_SETTINGS:
        registries_settings.append(settings.DY_DOCKER_HUB_REGISTRY_SETTINGS)

    await asyncio.get_event_loop().run_in_executor(
        None, create_docker_config_file, registries_settings
    )


def setup_registry(app: FastAPI) -> None:
    async def on_startup() -> None:
        settings: ApplicationSettings = app.state.settings
        await _login_registries(settings)

    app.add_event_handler("startup", on_startup)
