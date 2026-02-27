import pytest
from simcore_service_dynamic_scheduler.services.p_scheduler._models import SchedulerServiceStatus
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._models import ComponentPresence
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._status_legacy import (
    get_from_legacy_service,
)


@pytest.mark.parametrize(
    "presence, expected",
    [
        (ComponentPresence.ABSENT, SchedulerServiceStatus.IS_ABSENT),
        (ComponentPresence.STARTING, SchedulerServiceStatus.TRANSITION_TO_PRESENT),
        (ComponentPresence.RUNNING, SchedulerServiceStatus.IS_PRESENT),
        (ComponentPresence.FAILED, SchedulerServiceStatus.IN_ERROR),
    ],
)
def test_get_from_legacy_service(
    presence: ComponentPresence,
    expected: SchedulerServiceStatus,
) -> None:
    assert get_from_legacy_service(presence) == expected
