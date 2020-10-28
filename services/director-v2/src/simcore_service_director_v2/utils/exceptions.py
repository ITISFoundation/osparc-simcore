from typing import Optional


class DirectorException(Exception):
    """Basic exception for errors raised with director"""

    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unexpected error occurred in director subpackage")


from models_library.projects import ProjectID


class ProjectNotFoundError(DirectorException):
    """Service was not found in swarm"""

    def __init__(self, project_id: ProjectID):
        super().__init__(f"project {project_id} not found")
