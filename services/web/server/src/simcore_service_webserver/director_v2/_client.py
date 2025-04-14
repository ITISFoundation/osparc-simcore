"""Computations API

Wraps interactions to the director-v2 service

"""

import logging
from typing import Any

from aiohttp import web
from models_library.api_schemas_directorv2.computations import (
    ComputationCreate as DirectorV2ComputationCreate,
)
from models_library.projects import ProjectID
from models_library.users import UserID

from ._client_base import request_director_v2
from .settings import DirectorV2Settings, get_plugin_settings

_logger = logging.getLogger(__name__)


class ComputationsApi:
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._settings: DirectorV2Settings = get_plugin_settings(app)

    async def get(self, project_id: ProjectID, user_id: UserID) -> dict[str, Any]:
        computation_task_out = await request_director_v2(
            self._app,
            "GET",
            (self._settings.base_url / "computations" / f"{project_id}").with_query(
                user_id=int(user_id)
            ),
            expected_status=web.HTTPOk,
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    async def start(
        self, project_id: ProjectID, user_id: UserID, product_name: str, **options
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
                **options,
            ).model_dump(mode="json", exclude_unset=True),
        )
        assert isinstance(computation_task_out, dict)  # nosec
        computation_task_out_id: str = computation_task_out["id"]
        return computation_task_out_id

    async def stop(self, project_id: ProjectID, user_id: UserID):
        await request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations" / f"{project_id}:stop",
            expected_status=web.HTTPAccepted,
            data={"user_id": user_id},
        )


_APP_KEY = f"{__name__}.{ComputationsApi.__name__}"


def get_client(app: web.Application) -> ComputationsApi | None:
    app_key: ComputationsApi | None = app.get(_APP_KEY)
    return app_key


def set_client(app: web.Application, obj: ComputationsApi):
    app[_APP_KEY] = obj
