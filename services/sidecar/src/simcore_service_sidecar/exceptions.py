from typing import Optional


class SidecarException(Exception):
    """Basic exception for errors raised with sidecar"""

    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unexpected error occurred in director subpackage")


class DatabaseError(SidecarException):
    """Service was not found in swarm"""

    def __init__(self, msg: str):
        super().__init__(msg)


class TaskNotFound(SidecarException):
    """Task was not found """

    def __init__(self, msg: str):
        super().__init__(msg)


class MoreThenOneItemDetected(Exception):
    """Raised during the docker's container_id validation"""
    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unexpected error occurred in director subpackage")
