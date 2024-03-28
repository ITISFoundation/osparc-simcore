import asyncio
import base64
import json
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI
from settings_library.docker_registry import RegistrySettings
from starlette import status

from ..modules.service_liveness import wait_for_service_liveness

_logger = logging.getLogger(__name__)


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


async def wait_for_registry_liveness(app: FastAPI) -> None:
    registry_settings: RegistrySettings = app.state.settings.REGISTRY_SETTINGS

    await wait_for_service_liveness(
        _is_registry_reachable,
        service_name="Registry",
        endpoint=_get_registry_url(registry_settings),
        registry_settings=registry_settings,
    )


async def _login_registry(registry_settings: RegistrySettings) -> None:
    """
    Creates ~/.docker/config.json and adds docker registry credentials
    """

    def create_docker_config_file(registry_settings: RegistrySettings) -> None:
        user = registry_settings.REGISTRY_USER
        password = registry_settings.REGISTRY_PW.get_secret_value()
        docker_config = {
            "auths": {
                f"{registry_settings.resolved_registry_url}": {
                    "auth": base64.b64encode(f"{user}:{password}".encode()).decode(
                        "utf-8"
                    )
                }
            }
        }
        conf_file = Path.home() / ".docker" / "config.json"
        conf_file.parent.mkdir(exist_ok=True, parents=True)
        conf_file.write_text(json.dumps(docker_config))

    if registry_settings.REGISTRY_AUTH:
        await asyncio.get_event_loop().run_in_executor(
            None, create_docker_config_file, registry_settings
        )


def setup_registry(app: FastAPI) -> None:
    async def on_startup() -> None:
        registry_settings: RegistrySettings = app.state.settings.REGISTRY_SETTINGS
        await _login_registry(registry_settings)

    app.add_event_handler("startup", on_startup)
