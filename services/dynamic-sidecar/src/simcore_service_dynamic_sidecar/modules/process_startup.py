from time import monotonic
from typing import Final

from pydantic import PositiveFloat

_PROCESS_STARTUP_GRACE_S: Final[PositiveFloat] = 60


class ProcessStartupGrace:
    """Grants a newly (re)started worker process a grace period before its
    missing heart beats are considered a health degradation.
    """

    def __init__(self) -> None:
        self._process_started_at: float = monotonic()
        self._heart_beats_received: bool = False

    def on_process_restart(self) -> None:
        self._process_started_at = monotonic()
        self._heart_beats_received = False

    def on_heart_beats_received(self) -> None:
        self._heart_beats_received = True

    def in_startup_grace_period(self, *, process_running: bool) -> bool:
        return (
            not self._heart_beats_received
            and process_running
            and (monotonic() - self._process_started_at) < _PROCESS_STARTUP_GRACE_S
        )
