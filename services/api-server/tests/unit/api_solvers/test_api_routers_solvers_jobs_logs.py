# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import logging
from pprint import pprint
from typing import Final, Iterable

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.rabbitmq_messages import LoggerRabbitMessage
from pytest_mock import MockFixture
from pytest_simcore.simcore_webserver_projects_rest_api import GET_PROJECT
from respx import MockRouter
from servicelib.fastapi.rabbitmq import get_rabbitmq_client
from simcore_service_api_server.models.schemas.jobs import JobID, JobLog

_logger = logging.getLogger(__name__)
_faker = Faker()


@pytest.fixture
async def fake_rabbit_consumer(app: FastAPI):
    class FakeRabbitConsumer:
        _queue_name: Final[str] = "my_queue"
        _n_logs: int = 0
        _total_n_logs: int
        _produced_logs: list[str] = []

        async def subscribe(self, channel_name, callback, exclusive_queue, topics):
            async def produce_log():
                for _ in range(5):
                    txt = _faker.text()
                    self._produced_logs.append(txt)
                    msg = LoggerRabbitMessage(
                        user_id=_faker.pyint(),
                        project_id=_faker.uuid4(),
                        node_id=_faker.uuid4(),
                        messages=[txt],
                    )
                    await callback(msg.json())
                    await asyncio.sleep(0.2)

            asyncio.create_task(produce_log())
            return self._queue_name

        async def unsubscribe(self, queue_name):
            assert queue_name == self._queue_name

    fake_rabbit_consumer = FakeRabbitConsumer()
    app.dependency_overrides[get_rabbitmq_client] = lambda: fake_rabbit_consumer
    yield fake_rabbit_consumer


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
        "simcore_service_api_server.api.routes.solvers_jobs_getters._raise_if_job_not_associated_with_solver"
    )
    yield fake_project


async def test_log_streaming(
    app: FastAPI,
    auth: httpx.BasicAuth,
    client: httpx.AsyncClient,
    solver_key: str,
    solver_version: str,
    fake_rabbit_consumer,
    fake_project_for_streaming: ProjectGet,
    mocked_directorv2_service: MockRouter,
):

    job_id: JobID = fake_project_for_streaming.uuid

    collected_messages: list[str] = []
    async with client.stream(
        "GET",
        f"/v0/solvers/{solver_key}/releases/{solver_version}/jobs/{job_id}/logstream",
        auth=auth,
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            job_log = JobLog.parse_raw(line)
            pprint(job_log.json())
            collected_messages += job_log.messages

    assert (
        collected_messages
        == fake_rabbit_consumer._produced_logs[: len(collected_messages)]
    )
