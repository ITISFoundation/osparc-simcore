import bisect
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from pydantic import ByteSize, parse_obj_as

from ...models.dynamic_services_scheduler import SchedulerData

_KB = parse_obj_as(ByteSize, "1KiB")
_MB = parse_obj_as(ByteSize, "1MiB")
_GB = parse_obj_as(ByteSize, "1GiB")

_ITER_VALUES: Final[list[int]] = [*range(1, 10), *(x * 10 for x in range(1, 11))]

_SIZE_BUCKETS: Final[tuple[int, ...]] = (
    0,
    *(x * _KB for x in _ITER_VALUES),
    *(x * _MB for x in _ITER_VALUES),
    *(x * _GB for x in _ITER_VALUES),
)
SIZE_LABELS: Final[tuple[str, ...]] = tuple(f"{x}" for x in _SIZE_BUCKETS)

_SIZE_TO_LABELS: Final[dict[int, str]] = dict(
    zip(_SIZE_BUCKETS, SIZE_LABELS, strict=True)
)


def find_bucket(number: int) -> int:
    if number < _SIZE_BUCKETS[0]:
        return _SIZE_BUCKETS[0]
    if number >= _SIZE_BUCKETS[-1]:
        return _SIZE_BUCKETS[-1]
    index = bisect.bisect_left(_SIZE_BUCKETS, number)
    return _SIZE_BUCKETS[index]


def get_label_from_size(size: ByteSize | int) -> dict[str, str]:
    return {"byte_size": _SIZE_TO_LABELS[find_bucket(size)]}


def get_start_stop_labels(scheduler_data: "SchedulerData") -> dict[str, str]:
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
