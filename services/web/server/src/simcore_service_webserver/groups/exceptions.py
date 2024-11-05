"""Defines the different exceptions that may arise in the projects subpackage"""

from ..errors import WebServerBaseError


class GroupsError(WebServerBaseError):
    msg_template = "Groups plugin errored: {msg}"


class GroupNotFoundError(GroupsError):
    msg_template = "Group with id {gid} not found"


class UserInsufficientRightsError(GroupsError):
    msg = (
        "User {user_id} has insufficient rights for {permission} access to group {gid}"
    )


class UserInGroupNotFoundError(GroupsError):
    msg_template = "User id {uid} in Group {gid} not found"


class UserAlreadyInGroupError(GroupsError):
    msg_template = "User `{uid}` is already in Group `{gid}`"
