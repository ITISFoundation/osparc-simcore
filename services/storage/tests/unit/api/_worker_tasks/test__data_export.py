import re
from collections.abc import Callable

import pytest
from celery import Celery
from models_library.users import UserID
from simcore_service_storage.api._worker_tasks._data_export import data_export
from simcore_service_storage.modules.celery._task import define_task
from simcore_service_storage.modules.celery.client import CeleryTaskQueueClient
from simcore_service_storage.modules.celery.models import (
    TaskContext,
    TaskState,
)
from tenacity import Retrying, retry_if_exception_type, stop_after_delay, wait_fixed

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    def _(celery_app: Celery) -> None:
        define_task(celery_app, data_export)

    return _


@pytest.mark.usefixtures("celery_worker")
async def test_data_export(celery_client: CeleryTaskQueueClient, user_id: UserID):
    task_context = TaskContext()

    task_uuid = await celery_client.send_task(
        data_export.__name__,
        task_context=task_context,
        user_id=user_id,
        paths_to_export=[],
    )

    for attempt in Retrying(
        retry=retry_if_exception_type(AssertionError),
        wait=wait_fixed(1),
        stop=stop_after_delay(30),
    ):
        with attempt:
            status = await celery_client.get_task_status(task_context, task_uuid)
            assert status.task_state == TaskState.SUCCESS

    assert (
        await celery_client.get_task_status(task_context, task_uuid)
    ).task_state == TaskState.SUCCESS

    result = await celery_client.get_task_result(task_context, task_uuid)
    assert re.fullmatch(
        rf"^exports/{user_id}/[0-9a-fA-F]{{8}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{4}}-[0-9a-fA-F]{{12}}\.zip$",
        result,
    )
