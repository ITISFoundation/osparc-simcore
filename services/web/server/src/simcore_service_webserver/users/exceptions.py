from ..errors import WebServerBaseError


class UsersBaseError(WebServerBaseError):
    ...


class UserNotFoundError(UsersBaseError):
    def __init__(self, *, uid: int | None = None, email: str | None = None):
        self.uid = uid
        self.email = email
        self.msg_template = (
            "User id {uid} not found" if uid else f"User with email {email} not found"
        )


class TokenNotFoundError(UsersBaseError):
    msg_template = "Token for service {service_id} not found"

    def __init__(self, service_id: str):
        self.service_id = service_id


class UserDefaultWalletNotFoundError(UsersBaseError):
    msg_template = "Default wallet for user {uid} not found"

    def __init__(self, uid: int | None = None):
        self.uid = uid
