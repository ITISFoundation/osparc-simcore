from dataclasses import dataclass

from .._models import SchedulerServiceStatus
from ._models import ComponentPresence


@dataclass(frozen=True)
class ServiceSnapshot:
    sidecar: ComponentPresence
    proxy: ComponentPresence
    user_services: ComponentPresence  # ABSENT when sidecar isn't running yet


def get_from_new_style_service(snapshot: ServiceSnapshot) -> SchedulerServiceStatus:  # noqa: PLR0911
    sidecar, user_services, proxy = snapshot.sidecar, snapshot.user_services, snapshot.proxy

    # 1. Any failure → error
    if ComponentPresence.FAILED in (sidecar, user_services, proxy):
        return SchedulerServiceStatus.IN_ERROR

    # 2. Sidecar absent → service is absent (proxy must also be absent)
    if sidecar == ComponentPresence.ABSENT:
        return (
            SchedulerServiceStatus.IS_ABSENT if proxy == ComponentPresence.ABSENT else SchedulerServiceStatus.IN_ERROR
        )

    # 3. Sidecar starting → overall starting
    if sidecar == ComponentPresence.STARTING:
        return SchedulerServiceStatus.TRANSITION_TO_PRESENT

    # 4. Sidecar running → inspect downstream components
    assert sidecar == ComponentPresence.RUNNING

    if user_services == ComponentPresence.ABSENT:
        # Disambiguate startup vs shutdown by proxy state
        if proxy == ComponentPresence.RUNNING:
            # Containers removed but proxy still up → tearing down
            return SchedulerServiceStatus.TRANSITION_TO_ABSENT
        # Containers not yet created, proxy also absent → starting up
        return SchedulerServiceStatus.TRANSITION_TO_PRESENT

    if user_services == ComponentPresence.STARTING:
        return SchedulerServiceStatus.TRANSITION_TO_PRESENT

    # 5. containers == RUNNING
    if proxy == ComponentPresence.RUNNING:
        return SchedulerServiceStatus.IS_PRESENT
    # Proxy not yet up → last step of startup
    return SchedulerServiceStatus.TRANSITION_TO_PRESENT
