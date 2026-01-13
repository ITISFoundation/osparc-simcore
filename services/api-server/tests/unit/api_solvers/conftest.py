# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterable, Callable
from datetime import UTC, datetime, timedelta
from typing import Final

import httpx
import pytest
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.projects_state import RunningState
from pytest_mock import MockType
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
def mock_dependency_get_celery_task_manager(app: FastAPI, mock_task_manager_object: MockType) -> MockType:
    from simcore_service_api_server.api.dependencies.celery import get_task_manager  # noqa: PLC0415

    app.dependency_overrides[get_task_manager] = lambda: mock_task_manager_object
    yield mock_task_manager_object
    app.dependency_overrides.pop(get_task_manager, None)


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
    stop_time: Final[datetime] = datetime.now(tz=UTC) + timedelta(seconds=5)

    def _get_computation(request: httpx.Request, **kwargs) -> httpx.Response:
        task = ComputationTaskGet.model_validate(ComputationTaskGet.model_json_schema()["examples"][0])
        if datetime.now(tz=UTC) > stop_time:
            task.state = RunningState.SUCCESS
            task.stopped = datetime.now(tz=UTC)
        return httpx.Response(status_code=status.HTTP_200_OK, json=jsonable_encoder(task))

    mocked_directorv2_rest_api_base.get(
        path__regex=r"/v2/computations/(?P<project_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    ).mock(side_effect=_get_computation)
    return mocked_directorv2_rest_api_base
