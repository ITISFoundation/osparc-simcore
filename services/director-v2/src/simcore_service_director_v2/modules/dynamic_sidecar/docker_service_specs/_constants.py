from typing import Final

_SECOND: Final[int] = 1_000_000_000  # expressed in nano-seconds

DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS = {
    "Condition": "on-failure",
    "MaxAttempts": 0,
    "Delay": 5 * _SECOND,
}
