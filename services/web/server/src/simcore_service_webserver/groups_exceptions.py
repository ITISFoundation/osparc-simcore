"""Defines the different exceptions that may arise in the projects subpackage"""


class GroupsException(Exception):
    """Basic exception for errors raised in projects"""

    def __init__(self, msg: str = None):
        super().__init__(msg or "Unexpected error occured in projects subpackage")


class GroupNotFoundError(GroupsException):
    """Group was not found in DB"""

    def __init__(self, gid: int):
        super().__init__(f"Group with id {gid} not found")
        self.gid = gid


class UserInsufficientRightsError(GroupsException):
    """User has not sufficient rights"""

    def __init__(self, msg: str):
        super().__init__(msg)


class UserInGroupNotFoundError(GroupsException):
    """User in group was not found in DB"""

    def __init__(self, gid: int, uid: int):
        super().__init__(f"User id {uid} in Group {gid} not found")
        self.gid = gid
        self.uid = uid
