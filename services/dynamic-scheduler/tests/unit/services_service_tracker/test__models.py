import pytest
from faker import Faker
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    ServiceStates,
    TrackedServiceModel,
    UserRequestedState,
)


@pytest.mark.parametrize("requested_state", UserRequestedState)
@pytest.mark.parametrize("current_state", ServiceStates)
def test_serialization(
    faker: Faker, requested_state: UserRequestedState, current_state: ServiceStates
) -> None:
    tracked_model = TrackedServiceModel(
        service_status=faker.pystr(),
        requested_sate=requested_state,
        current_state=current_state,
    )

    as_bytes = tracked_model.to_bytes()
    assert as_bytes
    assert TrackedServiceModel.from_bytes(as_bytes) == tracked_model
