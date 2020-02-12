"""Defines the different exceptions that may arise in the projects subpackage"""

class ProjectsException(Exception):
    """Basic exception for errors raised in projects"""
    def __init__(self, msg=None):
        if msg is None:
            msg = "Unexpected error occured in projects subpackage"
        super(ProjectsException, self).__init__(msg)

class ProjectInvalidRightsError(ProjectsException):
    """Invalid rights to access project"""
    def __init__(self, user_id, project_uuid):
        msg = "User {} has no rights to access project with uuid {}".format(user_id, project_uuid)
        super(ProjectInvalidRightsError, self).__init__(msg)
        self.user_id = user_id
        self.project_uuid = project_uuid

class ProjectNotFoundError(ProjectsException):
    """Project was not found in DB"""
    def __init__(self, project_uuid):
        msg = "Project with uuid {} not found".format(project_uuid)
        super(ProjectNotFoundError, self).__init__(msg)
        self.project_uuid = project_uuid

class NodeNotFoundError(ProjectsException):
    """Node was not found in project"""
    def __init__(self, project_uuid: str, node_uuid: str):
        msg = f"Node {node_uuid} not found in project {project_uuid}"
        super(NodeNotFoundError, self).__init__(msg)
        self.node_uuid = node_uuid
        self.project_uuid = project_uuid
