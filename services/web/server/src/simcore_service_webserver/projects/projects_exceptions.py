"""Defines the different exceptions that may arise in the projects subpackage"""
import redis.exceptions
from models_library.projects import ProjectID
from models_library.users import UserID


class ProjectsException(Exception):
    """Basic exception for errors raised in projects"""

    def __init__(self, msg=None):
        super().__init__(msg or "Unexpected error occured in projects submodule")


class ProjectInvalidRightsError(ProjectsException):
    """Invalid rights to access project"""

    def __init__(self, user_id, project_uuid):
        super().__init__(
            f"User {user_id} has no rights to access project with uuid {project_uuid}"
        )
        self.user_id = user_id
        self.project_uuid = project_uuid


class ProjectOwnerNotFoundError(ProjectsException):
    """Project owner was not found"""

    def __init__(self, project_uuid):
        super().__init__(f"Project with uuid {project_uuid} has no project owner")
        self.project_uuid = project_uuid


class ProjectNotFoundError(ProjectsException):
    """Project was not found in DB"""

    def __init__(self, project_uuid):
        super().__init__(f"Project with uuid {project_uuid} not found")
        self.project_uuid = project_uuid


class ProjectDeleteError(ProjectsException):
    def __init__(self, project_uuid, reason):
        super().__init__(f"Failed to complete deletion of {project_uuid=}: {reason}")
        self.project_uuid = project_uuid


class NodeNotFoundError(ProjectsException):
    """Node was not found in project"""

    def __init__(self, project_uuid: str, node_uuid: str):
        super().__init__(f"Node {node_uuid} not found in project {project_uuid}")
        self.node_uuid = node_uuid
        self.project_uuid = project_uuid


ProjectLockError = redis.exceptions.LockError


class ProjectStartsTooManyDynamicNodes(ProjectsException):
    """user tried to start too many nodes concurrently"""

    def __init__(self, user_id: UserID, project_uuid: ProjectID):
        super().__init__(
            "The maximal amount of concurrently running dynamic services was reached. Please manually stop a service and retry."
        )
        self.user_id = user_id
        self.project_uuid = project_uuid


class ProjectTooManyProjectOpened(ProjectsException):
    def __init__(self, max_num_projects: int):
        super().__init__(
            f"You cannot open more than {max_num_projects} stud{'y' if max_num_projects == 1 else 'ies'} at once. Please, close another study and retry."
        )
