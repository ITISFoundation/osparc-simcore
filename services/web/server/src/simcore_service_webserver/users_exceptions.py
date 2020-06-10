"""Defines the different exceptions that may arise in the projects subpackage"""


class UsersException(Exception):
    """Basic exception for errors raised in projects"""

    def __init__(self, msg: str = None):
        super().__init__(msg or "Unexpected error occured in projects subpackage")


class UserNotFoundError(UsersException):
    """User in group was not found in DB"""

    def __init__(self, uid: int):
        super().__init__(f"User id {uid} not found")
        self.uid = uid


class GroupNotFoundError(UsersException):
    """Group was not found in DB"""

    def __init__(self, gid: int):
        super().__init__(f"Group with id {gid} not found")
        self.gid = gid


class UserInGroupNotFoundError(UsersException):
    """User in group was not found in DB"""

    def __init__(self, gid: int, uid: int):
        super().__init__(f"User id {uid} in Group {gid} not found")
        self.gid = gid
        self.uid = uid


class UserInsufficientRightsError(UsersException):
    """User has not sufficient rights"""

    def __init__(self, msg: str):
        super().__init__(msg)


class TokenNotFoundError(UsersException):
    """Token was not found in DB"""

    def __init__(self, service_id: str):
        super().__init__(f"Token for service {service_id} not found")
        self.service_id = service_id
