from typing import TypeAlias

import redis.exceptions
from common_library.errors_classes import OsparcErrorMixin


class BaseRedisError(OsparcErrorMixin, RuntimeError): ...


class CouldNotAcquireLockError(BaseRedisError):
    msg_template: str = "Lock {lock.name} could not be acquired!"


class CouldNotConnectToRedisError(BaseRedisError):
    msg_template: str = "Connection to '{dsn}' failed"


class LockLostError(BaseRedisError):
    msg_template: str = (
        "Lock {lock.name} has been lost (e.g. it could not be auto-extended!)"
        "TIP: check connection to Redis DBs or look for Synchronous "
        "code that might block the auto-extender task. Somehow the distributed lock disappeared!"
    )


ProjectLockError: TypeAlias = redis.exceptions.LockError  # NOTE: backwards compatible


class SemaphoreError(BaseRedisError):
    msg_template: str = "Unexpected error with semaphore '{name}' by this instance `{instance_id}`"


class SemaphoreAcquisitionError(SemaphoreError):
    msg_template: str = "Could not acquire semaphore '{name}' by this instance `{instance_id}`"


class SemaphoreNotAcquiredError(SemaphoreError):
    msg_template: str = "Semaphore '{name}' was not acquired by this instance `{instance_id}`"


class SemaphoreLostError(SemaphoreError):
    msg_template: str = "Semaphore '{name}' was lost by this instance `{instance_id}`"
