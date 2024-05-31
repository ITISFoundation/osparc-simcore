from datetime import timedelta

import arrow
import pytest
from faker import Faker
from servicelib.deferred_tasks import TaskUID
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    ServiceStates,
    TrackedServiceModel,
    UserRequestedState,
)


@pytest.mark.parametrize("requested_state", UserRequestedState)
@pytest.mark.parametrize("current_state", ServiceStates)
@pytest.mark.parametrize("check_status_after", [None, 1, arrow.utcnow().timestamp()])
@pytest.mark.parametrize("service_status_task_uid", [None, TaskUID("ok")])
def test_serialization(
    faker: Faker,
    requested_state: UserRequestedState,
    current_state: ServiceStates,
    check_status_after: float | None,
    service_status_task_uid: TaskUID | None,
):
    tracked_model = TrackedServiceModel(
        requested_sate=requested_state,
        current_state=current_state,
        service_status=faker.pystr(),
        check_status_after=check_status_after,
        service_status_task_uid=service_status_task_uid,
    )

    as_bytes = tracked_model.to_bytes()
    assert as_bytes
    assert TrackedServiceModel.from_bytes(as_bytes) == tracked_model


async def test_set_check_status_after_to():
    model = TrackedServiceModel(UserRequestedState.RUNNING)
    assert model.check_status_after is None

    delay = timedelta(seconds=4)

    before = (arrow.utcnow() + delay).timestamp()
    model.set_check_status_after_to(delay)
    after = (arrow.utcnow() + delay).timestamp()

    assert model.check_status_after
    assert before < model.check_status_after < after
