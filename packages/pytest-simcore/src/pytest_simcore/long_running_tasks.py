from datetime import timedelta

import pytest
from pytest_mock import MockerFixture


@pytest.fixture
async def fast_long_running_tasks_cancellation(
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "servicelib.long_running_tasks.task._CANCEL_TASKS_CHECK_INTERVAL",
        new=timedelta(seconds=1),
    )
