from typing import Final

_NANO: Final[int] = int(1e9)

SERVICE_RESTART_MAX_ATTEMPTS: Final[int] = 100
SERVICE_RESTART_DELAY_BETWEEN_RESTARTS_S: Final[int] = 1 * _NANO
