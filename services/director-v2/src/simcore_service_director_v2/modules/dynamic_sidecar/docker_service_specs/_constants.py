from typing import Final

_GIGA: Final[int] = int(1e9)
_DELAY_NS: Final[int] = 5 * _GIGA

DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS = {
    "Condition": "on-failure",
    "MaxAttempts": 100,
    "Delay": _DELAY_NS,
}
