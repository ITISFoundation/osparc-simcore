from typing import Final, Self, TypeAlias, TypedDict

from models_library.basic_types import UUIDStr
from models_library.users import UserID
from pydantic import BaseModel, ConfigDict
from pydantic.config import JsonDict

ALIVE_SUFFIX: Final[str] = "alive"  # points to a string type
RESOURCE_SUFFIX: Final[str] = "resources"  # points to a hash (like a dict) type
RedisHashKey: TypeAlias = str


class UserSession(BaseModel):
    """Parts of the key used in redis for a user-session"""

    user_id: UserID
    client_session_id: str

    def to_redis_hash_key(self) -> RedisHashKey:
        return ":".join(f"{k}={v}" for k, v in self.model_dump().items())

    @classmethod
    def from_redis_hash_key(cls, hash_key: RedisHashKey) -> Self:
        key = dict(x.split("=") for x in hash_key.split(":") if "=" in x)
        return cls.model_validate(key)

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "user_id": 7,
                        "client_session_id": "c7fc4985-f96a-4be3-a8ed-5a43b1aa15e2",
                    },
                    {
                        "user_id": 666,
                        "client_session_id": "*",
                    },
                ]
            }
        )

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra=_update_json_schema_extra,
    )


class ResourcesDict(TypedDict, total=False):
    """Field-value pairs of {user_id}:{client_session_id}:resources key"""

    project_id: UUIDStr
    socket_id: str


AliveSessions: TypeAlias = list[UserSession]
DeadSessions: TypeAlias = list[UserSession]
