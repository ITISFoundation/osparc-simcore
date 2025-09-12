from ._client import RedisClientSDK
from ._clients_manager import RedisClientsManager
from ._decorators import exclusive
from ._errors import (
    CouldNotAcquireLockError,
    CouldNotConnectToRedisError,
    LockLostError,
    ProjectLockError,
    SemaphoreAcquisitionError,
    SemaphoreNotAcquiredError,
)
from ._models import RedisManagerDBConfig
from ._project_document_version import (
    PROJECT_DB_UPDATE_REDIS_LOCK_KEY,
    PROJECT_DOCUMENT_VERSION_KEY,
    increment_and_return_project_document_version,
)
from ._project_lock import (
    get_project_locked_state,
    is_project_locked,
    with_project_locked,
)
from ._semaphore_decorator import with_limited_concurrency
from ._utils import handle_redis_returns_union_types

__all__: tuple[str, ...] = (
    "PROJECT_DB_UPDATE_REDIS_LOCK_KEY",
    "PROJECT_DOCUMENT_VERSION_KEY",
    "CouldNotAcquireLockError",
    "CouldNotConnectToRedisError",
    "LockLostError",
    "ProjectLockError",
    "RedisClientSDK",
    "RedisClientsManager",
    "RedisManagerDBConfig",
    "SemaphoreAcquisitionError",
    "SemaphoreNotAcquiredError",
    "exclusive",
    "get_project_locked_state",
    "handle_redis_returns_union_types",
    "increment_and_return_project_document_version",
    "is_project_locked",
    "with_limited_concurrency",
    "with_project_locked",
)
