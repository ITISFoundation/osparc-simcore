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
