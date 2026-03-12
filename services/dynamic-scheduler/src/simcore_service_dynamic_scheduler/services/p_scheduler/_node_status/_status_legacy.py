from .._models import SchedulerServiceStatus
from ._models import ComponentPresence


def get_from_legacy_service(presence: ComponentPresence) -> SchedulerServiceStatus:
    match presence:
        case ComponentPresence.ABSENT:
            return SchedulerServiceStatus.IS_ABSENT
        case ComponentPresence.STARTING:
            return SchedulerServiceStatus.TRANSITION_TO_PRESENT
        case ComponentPresence.RUNNING:
            return SchedulerServiceStatus.IS_PRESENT
        case ComponentPresence.FAILED:
            return SchedulerServiceStatus.IN_ERROR

    msg = f"Unhandled presence {presence=}"
    raise NotImplementedError(msg)
