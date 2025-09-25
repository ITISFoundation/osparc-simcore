"""Computations API

Wraps interactions to the director-v2 service

"""

import logging
from typing import Final

import aiohttp
from aiohttp import ClientTimeout, web
from models_library.api_schemas_directorv2.computations import (
    ComputationCreate as DirectorV2ComputationCreate,
)
from models_library.api_schemas_directorv2.computations import (
    ComputationGet as DirectorV2ComputationGet,
)
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import AnyHttpUrl, TypeAdapter

from ._client_base import request_director_v2
from .settings import DirectorV2Settings, get_client_session, get_plugin_settings

_logger = logging.getLogger(__name__)

SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)

APP_DIRECTOR_V2_CLIENT_KEY: Final = web.AppKey(
    "APP_DIRECTOR_V2_CLIENT_KEY", "DirectorV2RestClient"
)


async def is_healthy(app: web.Application) -> bool:
    try:
        session = get_client_session(app)
        settings: DirectorV2Settings = get_plugin_settings(app)
        health_check_url = settings.base_url.parent
        await session.get(
            url=health_check_url,
            ssl=False,
            raise_for_status=True,
            timeout=SERVICE_HEALTH_CHECK_TIMEOUT,
        )
        return True
    except (aiohttp.ClientError, TimeoutError) as err:
        _logger.warning("Director is NOT healthy: %s", err)
        return False


class DirectorV2RestClient:
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._settings: DirectorV2Settings = get_plugin_settings(app)

    async def get_computation(
        self, project_id: ProjectID, user_id: UserID
    ) -> DirectorV2ComputationGet:
        computation_task_out = await request_director_v2(
            self._app,
            "GET",
            (self._settings.base_url / "computations" / f"{project_id}").with_query(
                user_id=int(user_id)
            ),
            expected_status=web.HTTPOk,
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return DirectorV2ComputationGet.model_validate(computation_task_out)

    async def start_computation(
        self,
        project_id: ProjectID,
        user_id: UserID,
        product_name: str,
        product_api_base_url: str,
        **options,
    ) -> str:
        computation_task_out = await request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations",
            expected_status=web.HTTPCreated,
            data=DirectorV2ComputationCreate(
                user_id=user_id,
                project_id=project_id,
                product_name=product_name,
                product_api_base_url=TypeAdapter(AnyHttpUrl).validate_python(
                    product_api_base_url
                ),
                **options,
            ).model_dump(mode="json", exclude_unset=True),
        )
        assert isinstance(computation_task_out, dict)  # nosec
        computation_task_out_id: str = computation_task_out["id"]
        return computation_task_out_id

    async def stop_computation(self, project_id: ProjectID, user_id: UserID):
        await request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations" / f"{project_id}:stop",
            expected_status=web.HTTPAccepted,
            data={"user_id": user_id},
        )


def set_directorv2_client(app: web.Application, obj: DirectorV2RestClient):
    app[APP_DIRECTOR_V2_CLIENT_KEY] = obj


def get_directorv2_client(app: web.Application) -> DirectorV2RestClient:
    app_key: DirectorV2RestClient = app[APP_DIRECTOR_V2_CLIENT_KEY]
    return app_key
