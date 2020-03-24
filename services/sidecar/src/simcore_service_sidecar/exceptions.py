from typing import Optional


class SidecarException(Exception):
    """Basic exception for errors raised with sidecar"""

    def __init__(self, msg: Optional[str] = None):
        if msg is None:
            msg = "Unexpected error occured in director subpackage"
        super(SidecarException, self).__init__(msg)


class DatabaseError(SidecarException):
    """Service was not found in swarm"""

    def __init__(self, msg: str):
        super(DatabaseError, self).__init__(msg)
