from typing import Final

_NANO: Final[int] = int(1e9)

# task_template->ContainerSpec ...
DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS = {
    "Condition": "on-failure",
    "Delay": 100,
    "MaxAttempts": 1 * _NANO,
}
