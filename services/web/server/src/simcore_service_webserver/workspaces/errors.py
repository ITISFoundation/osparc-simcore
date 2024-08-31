from ..errors import WebServerBaseError


class WorkspacesValueError(WebServerBaseError, ValueError):
    ...


class WorkspaceNotFoundError(WorkspacesValueError):
    msg_template = "Workspace not found. {reason}"


class WorkspaceAccessForbiddenError(WorkspacesValueError):
    msg_template = "Workspace access forbidden. {reason}"


# Workspace groups


class WorkspaceGroupNotFoundError(WorkspacesValueError):
    msg_template = "Workspace group not found. {reason}"


# Workspace and Folder


class WorkspaceAndFolderIncompatibleError(WorkspacesValueError):
    msg_template = "Workspace {workspace_id} and Folder {folder_id} are incompatible"


# Workspace and Project
class WorkspaceAndProjectIncompatibleError(WorkspacesValueError):
    msg_template = "Workspace {workspace_id} and Project {project_id} are incompatible"
