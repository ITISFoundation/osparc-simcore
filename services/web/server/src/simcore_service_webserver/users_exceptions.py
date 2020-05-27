"""Defines the different exceptions that may arise in the projects subpackage"""


class UsersException(Exception):
    """Basic exception for errors raised in projects"""

    def __init__(self, msg=None):
        if msg is None:
            msg = "Unexpected error occured in projects subpackage"
        super(UsersException, self).__init__(msg)


class GroupNotFoundError(UsersException):
    """Group was not found in DB"""

    def __init__(self, gid):
        msg = "Group with id {} not found".format(gid)
        super(GroupNotFoundError, self).__init__(msg)
        self.gid = gid
