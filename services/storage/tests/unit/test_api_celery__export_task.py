from asyncio import AbstractEventLoop
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from models_library.projects_nodes_io import StorageFileID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from simcore_service_storage.api.celery._export_task import fake_celery_export

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def mock_rabbitmq_post_message(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch("simcore_service_storage.modules.rabbitmq.post_message")


async def test_celery_export_task(
    event_loop: AbstractEventLoop,
    initialized_app: FastAPI,
    mock_rabbitmq_post_message: AsyncMock,
):
    # TODO: rewrite this test with the Celery job subscription tests from GCR

    file_id = await event_loop.run_in_executor(
        None, fake_celery_export, event_loop, initialized_app, 1, []
    )

    # check progress values, since there are no files to read progress goes from 0 to 1
    assert mock_rabbitmq_post_message.call_count == 2
    progress_values = [
        x.args[1].report.actual_value for x in mock_rabbitmq_post_message.call_args_list
    ]
    assert progress_values == [0, 1]

    assert TypeAdapter(StorageFileID).validate_python(file_id)
