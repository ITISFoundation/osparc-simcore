import re

import pytest
from celery import Task
from models_library.progress_bar import ProgressReport, ProgressStructuredMessage
from models_library.users import UserID
from simcore_service_storage.api._worker_tasks._data_export import data_export

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]


@pytest.mark.usefixtures("celery_worker")
async def test_data_export(
    mock_task_progress: list[ProgressReport], fake_celery_task: Task, user_id: UserID
):
    result = await data_export(fake_celery_task, user_id=user_id, paths_to_export=[])
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
                description="create and upload export",
                current=0.0,
                total=1,
                unit=None,
                sub=None,
            ),
        ),
        ProgressReport(
            actual_value=1.0,
            total=1.0,
            attempt=0,
            unit=None,
            message=ProgressStructuredMessage(
                description="create and upload export",
                current=1.0,
                total=1,
                unit=None,
                sub=None,
            ),
        ),
    ]
