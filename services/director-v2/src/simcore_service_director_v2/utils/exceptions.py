from typing import Optional

from models_library.projects import ProjectID


class DirectorException(Exception):
    """Basic exception for errors raised with director"""

    def __init__(self, msg: Optional[str] = None):
        super().__init__(msg or "Unexpected error occurred in director subpackage")


class ProjectNotFoundError(DirectorException):
    """Project not found error"""

    def __init__(self, project_id: ProjectID):
        super().__init__(f"project {project_id} not found")


class PipelineNotFoundError(DirectorException):
    """Pipeline not found error"""

    def __init__(self, pipeline_id: str):
        super().__init__(f"pipeline {pipeline_id} not found")
