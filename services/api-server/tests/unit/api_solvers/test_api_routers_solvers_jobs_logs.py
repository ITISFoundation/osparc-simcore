# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from pprint import pprint
from typing import Final

import httpx
import pytest
from attr import dataclass
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.projects import ProjectGet
from pytest_mock import MockFixture
from pytest_simcore.simcore_webserver_projects_rest_api import GET_PROJECT
from respx import MockRouter
from simcore_service_api_server.api.dependencies.rabbitmq import get_log_distributor
from simcore_service_api_server.models.schemas.jobs import JobID, JobLog

_logger = logging.getLogger(__name__)
_faker = Faker()


@pytest.fixture
async def fake_log_distributor(app: FastAPI, mocker: MockFixture):
    @dataclass
    class FakeLogDistributor:
        _job_id: JobID | None = None
        _queue_name: Final[str] = "my_queue"
        _n_logs: int = 0
        _produced_logs: list[str] = []
        deregister_is_called: bool = False

        async def register(
            self, job_id: JobID, callback: Callable[[JobLog], Awaitable[None]]
        ):
            self._job_id = job_id

            async def produce_log():
                for _ in range(5):
                    txt = _faker.text()
                    self._produced_logs.append(txt)
                    msg = JobLog(
                        job_id=job_id,
                        node_id=_faker.uuid4(),
                        log_level=logging.INFO,
                        messages=[txt],
                    )
                    await callback(msg)
                    await asyncio.sleep(0.1)

            asyncio.create_task(produce_log())
            return self._queue_name

        async def deregister(self, job_id):
            assert self._job_id == job_id
            self.deregister_is_called = True

    fake_log_distributor = FakeLogDistributor()
    app.dependency_overrides[get_log_distributor] = lambda: fake_log_distributor
    yield fake_log_distributor
    assert fake_log_distributor.deregister_is_called


@pytest.fixture
def fake_project_for_streaming(
    app: FastAPI, mocker: MockFixture, faker: Faker
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
        "simcore_service_api_server.api.routes.solvers_jobs_getters.raise_if_job_not_associated_with_solver"
    )
    return fake_project


@pytest.mark.parametrize("disconnect", [True, False])
async def test_log_streaming(
    app: FastAPI,
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    fake_log_distributor,
    fake_project_for_streaming: ProjectGet,
    mocked_directorv2_service: MockRouter,
    disconnect: bool,
):

    job_id: JobID = fake_project_for_streaming.uuid

    collected_messages: list[str] = []
    async with client.stream(
        "GET",
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/logstream",
        auth=auth,
    ) as response:
        response.raise_for_status()
        if not disconnect:
            async for line in response.aiter_lines():
                job_log = JobLog.parse_raw(line)
                pprint(job_log.json())
                collected_messages += job_log.messages

    assert fake_log_distributor.deregister_is_called

    assert (
        collected_messages
        == fake_log_distributor._produced_logs[: len(collected_messages)]
    )
