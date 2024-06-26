from datetime import timedelta

import arrow
import pytest
from faker import Faker
from servicelib.deferred_tasks import TaskUID
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    SchedulerServiceState,
    TrackedServiceModel,
    UserRequestedState,
)


@pytest.mark.parametrize("requested_state", UserRequestedState)
@pytest.mark.parametrize("current_state", SchedulerServiceState)
@pytest.mark.parametrize("check_status_after", [1, arrow.utcnow().timestamp()])
@pytest.mark.parametrize("service_status_task_uid", [None, TaskUID("ok")])
def test_serialization(
    faker: Faker,
    requested_state: UserRequestedState,
    current_state: SchedulerServiceState,
    check_status_after: float,
    service_status_task_uid: TaskUID | None,
):
    tracked_model = TrackedServiceModel(
        dynamic_service_start=None,
        user_id=None,
        project_id=None,
        requested_state=requested_state,
        current_state=current_state,
        service_status=faker.pystr(),
        check_status_after=check_status_after,
        service_status_task_uid=service_status_task_uid,
    )

    as_bytes = tracked_model.to_bytes()
    assert as_bytes
    assert TrackedServiceModel.from_bytes(as_bytes) == tracked_model


async def test_set_check_status_after_to():
    model = TrackedServiceModel(
        dynamic_service_start=None,
        user_id=None,
        project_id=None,
        requested_state=UserRequestedState.RUNNING,
    )
    assert model.check_status_after < arrow.utcnow().timestamp()

    delay = timedelta(seconds=4)

    before = (arrow.utcnow() + delay).timestamp()
    model.set_check_status_after_to(delay)
    after = (arrow.utcnow() + delay).timestamp()

    assert model.check_status_after
    assert before < model.check_status_after < after
