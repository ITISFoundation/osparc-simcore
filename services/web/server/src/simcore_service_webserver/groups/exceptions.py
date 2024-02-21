"""Defines the different exceptions that may arise in the projects subpackage"""

from ..errors import WebServerError


class GroupsError(WebServerError):
    msg_template = "{msg}"

    def __init__(self, msg: str = None):
        super().__init__(msg=msg or "Unexpected error occured in projects subpackage")


class GroupNotFoundError(GroupsError):
    msg_template = "Group with id {gid} not found"


class UserInsufficientRightsError(GroupsError):
    ...


class UserInGroupNotFoundError(GroupsError):
    msg_template = "User id {uid} in Group {gid} not found"
