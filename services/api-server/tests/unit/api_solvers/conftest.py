# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterable, Callable
from datetime import datetime, timedelta
from typing import Final

import httpx
import pytest
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.projects_state import RunningState
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.services_http.director_v2 import ComputationTaskGet


@pytest.fixture
def solver_key() -> str:
    return "simcore/services/comp/itis/sleeper"


@pytest.fixture
def solver_version() -> str:
    return "2.0.0"


@pytest.fixture
def mocked_webserver_rest_api(
    app: FastAPI,
    mocked_webserver_rest_api_base: MockRouter,
    patch_webserver_long_running_project_tasks: Callable[[MockRouter], MockRouter],
) -> MockRouter:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    patch_webserver_long_running_project_tasks(mocked_webserver_rest_api_base)

    return mocked_webserver_rest_api_base


@pytest.fixture
async def mocked_directorv2_rest_api(
    mocked_directorv2_rest_api_base,
) -> AsyncIterable[MockRouter]:
    stop_time: Final[datetime] = datetime.now() + timedelta(seconds=5)

    def _get_computation(request: httpx.Request, **kwargs) -> httpx.Response:
        task = ComputationTaskGet.model_validate(
            ComputationTaskGet.model_json_schema()["examples"][0]
        )
        if datetime.now() > stop_time:
            task.state = RunningState.SUCCESS
            task.stopped = datetime.now()
        return httpx.Response(
            status_code=status.HTTP_200_OK, json=jsonable_encoder(task)
        )

    mocked_directorv2_rest_api_base.get(
        path__regex=r"/v2/computations/(?P<project_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    ).mock(side_effect=_get_computation)
    return mocked_directorv2_rest_api_base
