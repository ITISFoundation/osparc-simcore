"""Defines the different exceptions that may arise in the projects subpackage"""


class UsersException(Exception):
    """Basic exception for errors raised in projects"""

    def __init__(self, msg=None):
        if msg is None:
            msg = "Unexpected error occured in projects subpackage"
        super(UsersException, self).__init__(msg)


class UserNotFoundError(UsersException):
    """User in group was not found in DB"""

    def __init__(self, uid):
        msg = "User id {} not found".format(uid)
        super(UserNotFoundError, self).__init__(msg)
        self.uid = uid


class GroupNotFoundError(UsersException):
    """Group was not found in DB"""

    def __init__(self, gid):
        msg = "Group with id {} not found".format(gid)
        super(GroupNotFoundError, self).__init__(msg)
        self.gid = gid


class UserInGroupNotFoundError(UsersException):
    """User in group was not found in DB"""

    def __init__(self, gid, uid):
        msg = "User id {} in Group {} not found".format(uid, gid)
        super(UserInGroupNotFoundError, self).__init__(msg)
        self.gid = gid
        self.uid = uid
