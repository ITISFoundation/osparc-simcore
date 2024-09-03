from ..errors import WebServerBaseError


class WorkspacesValueError(WebServerBaseError, ValueError):
    ...


class WorkspaceNotFoundError(WorkspacesValueError):
    msg_template = "Workspace not found. {reason}"


class WorkspaceAccessForbiddenError(WorkspacesValueError):
    msg_template = "Workspace access forbidden. {reason}"


# Workspace groups


class WorkspaceGroupNotFoundError(WorkspacesValueError):
    msg_template = "Workspace {workspace_id} group {group_id} not found."


class WorkspaceFolderInconsistencyError(WorkspacesValueError):
    msg_template = "Folder {folder_id} does not exists in the workspace {workspace_id}"
