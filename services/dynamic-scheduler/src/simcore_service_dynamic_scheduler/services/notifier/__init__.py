from ._notifier import notify_service_status_change
from ._setup import configure_notifier

__all__: tuple[str, ...] = (
    "configure_notifier",
    "notify_service_status_change",
)
