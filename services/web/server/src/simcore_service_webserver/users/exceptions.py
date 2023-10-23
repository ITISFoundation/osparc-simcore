"""Defines the different exceptions that may arise in the projects subpackage"""


class UsersException(Exception):
    """Basic exception for errors raised in projects"""

    def __init__(self, msg: str = None):
        super().__init__(msg or "Unexpected error occured in projects subpackage")


class UserNotFoundError(UsersException):
    """User in group was not found in DB"""

    def __init__(self, *, uid: int | None = None, email: str | None = None):
        super().__init__(
            f"User id {uid} not found" if uid else f"User with email {email} not found"
        )
        self.uid = uid
        self.email = email


class TokenNotFoundError(UsersException):
    """Token was not found in DB"""

    def __init__(self, service_id: str):
        super().__init__(f"Token for service {service_id} not found")
        self.service_id = service_id


class UserDefaultWalletNotFoundError(UsersException):
    def __init__(self, uid: int | None = None):
        super().__init__(f"Default wallet for user {uid} not found")
        self.uid = uid
