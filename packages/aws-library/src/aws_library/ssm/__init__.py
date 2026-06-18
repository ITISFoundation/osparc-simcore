from ._client import SimcoreSSMAPI
from ._errors import (
    SSMAccessError,
    SSMCommandExecutionResultError,
    SSMCommandExecutionTimeoutError,
    SSMInvalidCommandError,
    SSMNotConnectedError,
    SSMRuntimeError,
    SSMSendCommandInstancesNotReadyError,
)
from ._fastapi_lifespan import configure_ssm_client

__all__: tuple[str, ...] = (
    "SSMAccessError",
    "SSMCommandExecutionResultError",
    "SSMCommandExecutionTimeoutError",
    "SSMInvalidCommandError",
    "SSMNotConnectedError",
    "SSMRuntimeError",
    "SSMSendCommandInstancesNotReadyError",
    "SimcoreSSMAPI",
    "configure_ssm_client",
)
