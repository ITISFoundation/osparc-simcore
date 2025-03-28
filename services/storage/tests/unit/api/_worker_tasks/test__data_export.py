# pylint:disable=redefined-outer-name

import re

import pytest
from celery import Task
from faker import Faker
from models_library.progress_bar import ProgressReport, ProgressStructuredMessage
from models_library.users import UserID
from simcore_service_storage.api._worker_tasks._simcore_s3 import data_export
from simcore_service_storage.modules.celery.models import TaskID

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]


@pytest.fixture
def fake_task_id(faker: Faker) -> TaskID:
    return f"{faker.uuid4()}"


@pytest.mark.usefixtures("celery_worker")
async def test_data_export(
    mock_task_progress: list[ProgressReport],
    fake_celery_task: Task,
    user_id: UserID,
    fake_task_id: TaskID,
):
    result = await data_export(
        fake_celery_task, fake_task_id, user_id=user_id, paths_to_export=[]
    )
    assert re.fullmatch(
        rf"^exports/{user_id}/[0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}}\.zip$",
        result,
    )

    assert mock_task_progress == [
        ProgressReport(
            actual_value=0.0,
            total=1.0,
            attempt=0,
            unit=None,
            message=ProgressStructuredMessage(
                description="data export", current=0.0, total=1, unit=None, sub=None
            ),
        ),
        ProgressReport(
            actual_value=1.0,
            total=1.0,
            attempt=0,
            unit=None,
            message=ProgressStructuredMessage(
                description="data export", current=1.0, total=1, unit=None, sub=None
            ),
        ),
    ]
