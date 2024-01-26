from pydantic import parse_obj_as

from ..basic_types import IDStr
from ..users import GroupID, UserID


class SocketIORoomStr(IDStr):
    @classmethod
    def from_socket_id(cls, socket_id: str) -> "SocketIORoomStr":
        return parse_obj_as(cls, socket_id)

    @classmethod
    def from_group_id(cls, group_id: GroupID) -> "SocketIORoomStr":
        return parse_obj_as(cls, f"group:{group_id}")

    @classmethod
    def from_user_id(cls, user_id: UserID) -> "SocketIORoomStr":
        return parse_obj_as(cls, f"user:{user_id}")
