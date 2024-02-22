"""Defines the different exceptions that may arise in the projects subpackage"""
from typing import Any

import redis.exceptions
from models_library.projects import ProjectID
from models_library.users import UserID

from ..errors import WebServerBaseError


class BaseProjectError(WebServerBaseError):
    msg_template = "Unexpected error occured in projects submodule"

    def __init__(self, msg=None, **ctx):
        super().__init__(**ctx)
        if msg:
            self.msg_template = msg

    def debug_message(self):
        # Override in subclass
        return f"{self.code}: {self}"


class ProjectInvalidUsageError(BaseProjectError):
    ...


class ProjectInvalidRightsError(BaseProjectError):
    msg_template = (
        "User '{user_id}' has no rights to access project with uuid '{project_uuid}'"
    )

    def __init__(self, *, user_id, project_uuid, **ctx):
        super().__init__(**ctx)
        self.user_id = user_id
        self.project_uuid = project_uuid


class ProjectOwnerNotFoundError(BaseProjectError):
    msg_template = "Project with uuid '{project_uuid}' has no project owner"

    def __init__(self, *, project_uuid, **ctx):
        super().__init__(**ctx)
        self.project_uuid = project_uuid


class ProjectNotFoundError(BaseProjectError):
    msg_template = "Project with uuid '{project_uuid}' not found."

    def __init__(self, project_uuid, *, search_context: Any | None = None, **ctx):
        super().__init__(**ctx)
        self.project_uuid = project_uuid
        self.search_context_msg = f"{search_context}"

    def debug_message(self):
        msg = f"{self.code}: Project with uuid '{self.project_uuid}'"
        if self.search_context_msg:
            msg += f" and {self.search_context_msg}"
        msg += " was not found"
        return msg


class ProjectDeleteError(BaseProjectError):
    msg_template = "Failed to complete deletion of '{project_uuid}': {reason}"

    def __init__(self, *, project_uuid, reason, **ctx):
        super().__init__(**ctx)
        self.project_uuid = project_uuid
        self.reason = reason


class NodeNotFoundError(BaseProjectError):
    msg_template = "Node '{node_uuid}' not found in project '{project_uuid}'"

    def __init__(self, *, project_uuid: str, node_uuid: str, **ctx):
        super().__init__(**ctx)
        self.node_uuid = node_uuid
        self.project_uuid = project_uuid


ProjectLockError = redis.exceptions.LockError


class ProjectStartsTooManyDynamicNodesError(BaseProjectError):
    msg_template = "The maximal amount of concurrently running dynamic services was reached. Please manually stop a service and retry."

    def __init__(self, *, user_id: UserID, project_uuid: ProjectID, **ctx):
        super().__init__(**ctx)
        self.user_id = user_id
        self.project_uuid = project_uuid


class ProjectTooManyProjectOpenedError(BaseProjectError):
    msg_template = "You cannot open more than {max_num_projects} study/ies at once. Please close another study and retry."

    def __init__(self, *, max_num_projects: int, **ctx):
        super().__init__(**ctx)
        self.max_num_projects = max_num_projects


class PermalinkNotAllowedError(BaseProjectError):
    ...


class PermalinkFactoryError(BaseProjectError):
    ...


class ProjectNodeResourcesInvalidError(BaseProjectError):
    ...


class ProjectNodeResourcesInsufficientRightsError(BaseProjectError):
    ...


class DefaultPricingUnitNotFoundError(BaseProjectError):
    msg_template = "Default pricing unit not found for node '{node_uuid}' in project '{project_uuid}'"

    def __init__(self, *, project_uuid: str, node_uuid: str, **ctxs):
        super().__init__(**ctxs)
        self.node_uuid = node_uuid
        self.project_uuid = project_uuid


class ClustersKeeperNotAvailableError(BaseProjectError):
    """Clusters-keeper service is not available"""


class InvalidInputValue(WebServerBaseError):
    msg_template = "Invalid value for input '{node_id}': {message} for value={value}"
