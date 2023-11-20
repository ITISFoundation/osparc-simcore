# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import logging
from typing import Iterable

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.projects import ProjectGet
from pytest_mock import MockFixture
from pytest_simcore.simcore_webserver_projects_rest_api import GET_PROJECT
from simcore_service_api_server.models.schemas.jobs import JobID, JobLog

_logger = logging.getLogger(__name__)


@pytest.fixture
def fake_project_for_streaming(
    mocker: MockFixture, faker: Faker
) -> Iterable[ProjectGet]:

    assert isinstance(response_body := GET_PROJECT.response_body, dict)
    assert (data := response_body.get("data")) is not None
    fake_project = ProjectGet.parse_obj(data)
    fake_project.workbench = {faker.uuid4(): faker.uuid4()}
    mocker.patch(
        "simcore_service_api_server.api.dependencies.webserver.AuthSession.get_project",
        return_value=fake_project,
    )

    mocker.patch(
        "simcore_service_api_server.api.routes.solvers_jobs_getters._raise_if_job_not_associated_with_solver"
    )
    yield fake_project


async def test_log_streaming(
    app: FastAPI,
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    fake_project_for_streaming: ProjectGet,
):

    job_id: JobID = fake_project_for_streaming.uuid

    ii: int = 0
    async with client.stream(
        "GET",
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/logstream",
        auth=auth,
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            job_log = JobLog.parse_raw(line)
            _logger.debug(job_log.json())
            ii += 1
    assert ii > 0
