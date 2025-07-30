from ..errors import WebServerBaseError


class WorkspacesValueError(WebServerBaseError, ValueError): ...


class WorkspacesRuntimeError(WebServerBaseError, RuntimeError): ...


class WorkspaceNotFoundError(WorkspacesValueError):
    msg_template = "Workspace not found: {details}"


class WorkspaceAccessForbiddenError(WorkspacesValueError):
    msg_template = "Workspace access forbidden: {details}"


class WorkspaceBatchDeleteError(WorkspacesValueError):
    msg_template = "One or more workspaces could not be deleted: {errors}"


# Workspace groups


class WorkspaceGroupNotFoundError(WorkspacesValueError):
    msg_template = "Workspace {workspace_id} group {group_id} not found."


class WorkspaceFolderInconsistencyError(WorkspacesValueError):
    msg_template = "Folder {folder_id} does not exists in the workspace {workspace_id}"


class WorkspaceNotTrashedError(WorkspacesRuntimeError):
    msg_template = "Cannot delete workspace {workspace_id} since it was not trashed first: {details}"
