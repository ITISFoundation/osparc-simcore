import time
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import NonNegativeFloat

from ...models.dynamic_services_scheduler import SchedulerData


def get_metrics_labels(scheduler_data: "SchedulerData") -> dict[str, str]:
    return {
        "user_id": f"{scheduler_data.user_id}",
        "wallet_id": (
            f"{scheduler_data.wallet_info.wallet_id}"
            if scheduler_data.wallet_info
            else ""
        ),
        "service_key": scheduler_data.key,
        "service_version": scheduler_data.version,
    }


def get_rate(size: NonNegativeFloat, duration: NonNegativeFloat) -> NonNegativeFloat:
    return size / duration


class DeferredFloat:
    def __init__(self):
        self._value: float | None = None

    def set_value(self, value):
        if not isinstance(value, float | int):
            msg = "Value must be a float or an int."
            raise TypeError(msg)

        self._value = float(value)

    def to_flaot(self) -> float:
        if not isinstance(self._value, float):
            msg = "Value must be a float or an int."
            raise TypeError(msg)

        return self._value


@contextmanager
def track_duration() -> Iterator[DeferredFloat]:
    duration = DeferredFloat()
    start_time = time.time()

    yield duration

    end_time = time.time()
    duration.set_value(end_time - start_time)
