from ..users import GroupID, UserID


class SocketIORoom(str):
    __slots__ = ()

    @classmethod
    def from_socket_id(cls, socket_id: str) -> "SocketIORoom":
        return cls(socket_id)

    @classmethod
    def from_group_id(cls, group_id: GroupID) -> "SocketIORoom":
        return cls(group_id)

    @classmethod
    def from_user_id(cls, user_id: UserID) -> "SocketIORoom":
        return cls(f"user:{user_id}")
