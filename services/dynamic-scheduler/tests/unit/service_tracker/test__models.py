import asyncio

import arrow
import pytest
from faker import Faker
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    _SECONDS_TO_TRIGGER_SERVICE_CHECKING,
    ServiceStates,
    TrackedServiceModel,
    UserRequestedState,
)


@pytest.mark.parametrize("requested_state", UserRequestedState)
@pytest.mark.parametrize("current_state", ServiceStates)
@pytest.mark.parametrize("last_checked", [None, 1, arrow.utcnow().timestamp()])
def test_serialization(
    faker: Faker,
    requested_state: UserRequestedState,
    current_state: ServiceStates,
    last_checked: float,
):
    tracked_model = TrackedServiceModel(
        service_status=faker.pystr(),
        requested_sate=requested_state,
        current_state=current_state,
        last_checked=last_checked,
    )

    as_bytes = tracked_model.to_bytes()
    assert as_bytes
    assert TrackedServiceModel.from_bytes(as_bytes) == tracked_model


async def test_last_checked():
    model = TrackedServiceModel(UserRequestedState.RUNNING)

    # when last_checked is None
    assert model.seconds_since_last_check() == _SECONDS_TO_TRIGGER_SERVICE_CHECKING

    model.set_last_checked_to_now()

    assert model.seconds_since_last_check() < 0.1

    await asyncio.sleep(0.1)

    assert model.seconds_since_last_check() > 0.1
