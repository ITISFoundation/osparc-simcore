import pytest
from simcore_service_dynamic_scheduler.services.p_scheduler._models import SchedulerServiceStatus
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._models import ComponentPresence
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._status_new_style import (
    ServiceSnapshot,
    get_from_new_style_service,
)

_A = ComponentPresence.ABSENT
_S = ComponentPresence.STARTING
_R = ComponentPresence.RUNNING
_F = ComponentPresence.FAILED

_ABSENT = SchedulerServiceStatus.IS_ABSENT
_PRESENT = SchedulerServiceStatus.IS_PRESENT
_TO_PRESENT = SchedulerServiceStatus.TRANSITION_TO_PRESENT
_TO_ABSENT = SchedulerServiceStatus.TRANSITION_TO_ABSENT
_ERROR = SchedulerServiceStatus.IN_ERROR


@pytest.mark.parametrize(
    "sidecar, proxy, user_services, expected",
    [
        # --- sidecar ABSENT: absent if proxy also absent, error otherwise ---
        (_A, _A, _A, _ABSENT),
        (_A, _A, _S, _ABSENT),
        (_A, _A, _R, _ABSENT),
        (_A, _A, _F, _ERROR),  # user_services failed
        (_A, _S, _A, _ERROR),  # orphaned proxy
        (_A, _S, _S, _ERROR),  # orphaned proxy
        (_A, _S, _R, _ERROR),  # orphaned proxy
        (_A, _S, _F, _ERROR),  # failure
        (_A, _R, _A, _ERROR),  # orphaned proxy
        (_A, _R, _S, _ERROR),  # orphaned proxy
        (_A, _R, _R, _ERROR),  # orphaned proxy
        (_A, _R, _F, _ERROR),  # failure
        (_A, _F, _A, _ERROR),  # failure
        (_A, _F, _S, _ERROR),  # failure
        (_A, _F, _R, _ERROR),  # failure
        (_A, _F, _F, _ERROR),  # failure
        # --- sidecar STARTING: always transitioning to present (unless failure) ---
        (_S, _A, _A, _TO_PRESENT),
        (_S, _A, _S, _TO_PRESENT),
        (_S, _A, _R, _TO_PRESENT),
        (_S, _A, _F, _ERROR),  # failure
        (_S, _S, _A, _TO_PRESENT),
        (_S, _S, _S, _TO_PRESENT),
        (_S, _S, _R, _TO_PRESENT),
        (_S, _S, _F, _ERROR),  # failure
        (_S, _R, _A, _TO_PRESENT),
        (_S, _R, _S, _TO_PRESENT),
        (_S, _R, _R, _TO_PRESENT),
        (_S, _R, _F, _ERROR),  # failure
        (_S, _F, _A, _ERROR),  # failure
        (_S, _F, _S, _ERROR),  # failure
        (_S, _F, _R, _ERROR),  # failure
        (_S, _F, _F, _ERROR),  # failure
        # --- sidecar RUNNING, user_services ABSENT: startup vs shutdown ---
        (_R, _A, _A, _TO_PRESENT),  # startup: containers & proxy not yet created
        (_R, _S, _A, _TO_PRESENT),  # startup: containers not yet created, proxy starting
        (_R, _R, _A, _TO_ABSENT),  # shutdown: containers removed, proxy still up
        (_R, _F, _A, _ERROR),  # failure: proxy failed
        # --- sidecar RUNNING, user_services STARTING ---
        (_R, _A, _S, _TO_PRESENT),  # startup: containers starting, proxy absent
        (_R, _S, _S, _TO_PRESENT),  # startup: containers starting, proxy starting
        (_R, _R, _S, _TO_PRESENT),  # startup: containers starting, proxy running
        (_R, _F, _S, _ERROR),  # failure: proxy failed
        # --- sidecar RUNNING, user_services RUNNING ---
        (_R, _A, _R, _TO_PRESENT),  # startup: proxy not yet up (last step)
        (_R, _S, _R, _TO_PRESENT),  # startup: proxy starting (last step)
        (_R, _R, _R, _PRESENT),  # fully operational
        (_R, _F, _R, _ERROR),  # failure: proxy failed
        # --- sidecar RUNNING, user_services FAILED ---
        (_R, _A, _F, _ERROR),  # failure
        (_R, _S, _F, _ERROR),  # failure
        (_R, _R, _F, _ERROR),  # failure
        (_R, _F, _F, _ERROR),  # failure
        # --- sidecar FAILED: always error ---
        (_F, _A, _A, _ERROR),
        (_F, _A, _S, _ERROR),
        (_F, _A, _R, _ERROR),
        (_F, _A, _F, _ERROR),
        (_F, _S, _A, _ERROR),
        (_F, _S, _S, _ERROR),
        (_F, _S, _R, _ERROR),
        (_F, _S, _F, _ERROR),
        (_F, _R, _A, _ERROR),
        (_F, _R, _S, _ERROR),
        (_F, _R, _R, _ERROR),
        (_F, _R, _F, _ERROR),
        (_F, _F, _A, _ERROR),
        (_F, _F, _S, _ERROR),
        (_F, _F, _R, _ERROR),
        (_F, _F, _F, _ERROR),
    ],
)
def test_get_from_new_style_service(
    sidecar: ComponentPresence,
    proxy: ComponentPresence,
    user_services: ComponentPresence,
    expected: SchedulerServiceStatus,
) -> None:
    assert (
        get_from_new_style_service(ServiceSnapshot(sidecar=sidecar, proxy=proxy, user_services=user_services))
        == expected
    )
