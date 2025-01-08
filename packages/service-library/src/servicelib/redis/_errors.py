from common_library.errors_classes import OsparcErrorMixin


class BaseRedisError(OsparcErrorMixin, RuntimeError):
    ...


class CouldNotAcquireLockError(BaseRedisError):
    msg_template: str = "Lock {lock.name} could not be acquired!"


class CouldNotConnectToRedisError(BaseRedisError):
    msg_template: str = "Connection to '{dsn}' failed"


class LockLostError(BaseRedisError):
    msg_template: str = "Lock {lock.name} has been lost"
