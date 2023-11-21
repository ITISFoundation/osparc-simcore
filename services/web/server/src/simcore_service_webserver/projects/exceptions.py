"""Defines the different exceptions that may arise in the projects subpackage"""
from typing import Any

import redis.exceptions
from models_library.projects import ProjectID
from models_library.users import UserID


class BaseProjectError(Exception):
    """Basic exception for errors raised in projects"""

    def __init__(self, msg=None):
        super().__init__(msg or "Unexpected error occured in projects submodule")

    def detailed_message(self):
        # Override in subclass
        return f"{type(self)}: {self}"


class ProjectInvalidUsageError(BaseProjectError):
    ...


class ProjectInvalidRightsError(BaseProjectError):
    """Invalid rights to access project"""

    def __init__(self, user_id, project_uuid):
        super().__init__(
            f"User {user_id} has no rights to access project with uuid {project_uuid}"
        )
        self.user_id = user_id
        self.project_uuid = project_uuid


class ProjectOwnerNotFoundError(BaseProjectError):
    """Project owner was not found"""

    def __init__(self, project_uuid):
        super().__init__(f"Project with uuid {project_uuid} has no project owner")
        self.project_uuid = project_uuid


class ProjectNotFoundError(BaseProjectError):
    """Project was not found in DB"""

    def __init__(self, project_uuid, *, search_context: Any | None = None):
        super().__init__(f"Project with uuid {project_uuid} not found.")
        self.project_uuid = project_uuid
        self.search_context_msg = f"{search_context}"

    def detailed_message(self):
        msg = f"Project with uuid {self.project_uuid}"
        if self.search_context_msg:
            msg += f" and {self.search_context_msg}"
        msg += " was not found"
        return msg


class ProjectDeleteError(BaseProjectError):
    def __init__(self, project_uuid, reason):
        super().__init__(f"Failed to complete deletion of {project_uuid=}: {reason}")
        self.project_uuid = project_uuid


class NodeNotFoundError(BaseProjectError):
    """Node was not found in project"""

    def __init__(self, project_uuid: str, node_uuid: str):
        super().__init__(f"Node {node_uuid} not found in project {project_uuid}")
        self.node_uuid = node_uuid
        self.project_uuid = project_uuid


ProjectLockError = redis.exceptions.LockError


class ProjectStartsTooManyDynamicNodesError(BaseProjectError):
    """user tried to start too many nodes concurrently"""

    def __init__(self, user_id: UserID, project_uuid: ProjectID):
        super().__init__(
            "The maximal amount of concurrently running dynamic services was reached. Please manually stop a service and retry."
        )
        self.user_id = user_id
        self.project_uuid = project_uuid


class ProjectTooManyProjectOpenedError(BaseProjectError):
    def __init__(self, max_num_projects: int):
        super().__init__(
            f"You cannot open more than {max_num_projects} stud{'y' if max_num_projects == 1 else 'ies'} at once. Please close another study and retry."
        )


class PermalinkNotAllowedError(BaseProjectError):
    ...


class PermalinkFactoryError(BaseProjectError):
    ...


class ProjectNodeResourcesInvalidError(BaseProjectError):
    ...


class ProjectNodeResourcesInsufficientRightsError(BaseProjectError):
    ...


class DefaultPricingUnitNotFoundError(BaseProjectError):
    """Node was not found in project"""

    def __init__(self, project_uuid: str, node_uuid: str):
        super().__init__(
            f"Default pricing unit not found for node {node_uuid} in project {project_uuid}"
        )
        self.node_uuid = node_uuid
        self.project_uuid = project_uuid
