from common_library.pydantic_basic_types import IDStr

from ..users import GroupID, UserID


class SocketIORoomStr(IDStr):
    @classmethod
    def from_socket_id(cls, socket_id: str) -> "SocketIORoomStr":
        return cls(socket_id)

    @classmethod
    def from_group_id(cls, group_id: GroupID) -> "SocketIORoomStr":
        return cls(f"group:{group_id}")

    @classmethod
    def from_user_id(cls, user_id: UserID) -> "SocketIORoomStr":
        return cls(f"user:{user_id}")
