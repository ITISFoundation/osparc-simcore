from ._client import RedisClientSDK
from ._clients_manager import RedisClientsManager
from ._decorators import exclusive
from ._errors import (
    CouldNotAcquireLockError,
    CouldNotConnectToRedisError,
    LockLostError,
    ProjectLockError,
)
from ._models import RedisManagerDBConfig
from ._project_document_version import (
    PROJECT_DB_UPDATE_REDIS_LOCK_KEY,
    PROJECT_DOCUMENT_VERSION_KEY,
    get_and_increment_project_document_version,
    get_project_document_version,
)
from ._project_lock import (
    get_project_locked_state,
    is_project_locked,
    with_project_locked,
)
from ._utils import handle_redis_returns_union_types

__all__: tuple[str, ...] = (
    "CouldNotAcquireLockError",
    "CouldNotConnectToRedisError",
    "exclusive",
    "get_and_increment_project_document_version",
    "get_project_document_version",
    "get_project_locked_state",
    "handle_redis_returns_union_types",
    "is_project_locked",
    "LockLostError",
    "PROJECT_DB_UPDATE_REDIS_LOCK_KEY",
    "PROJECT_DOCUMENT_VERSION_KEY",
    "ProjectLockError",
    "RedisClientSDK",
    "RedisClientsManager",
    "RedisManagerDBConfig",
    "with_project_locked",
)

# nopycln: file
