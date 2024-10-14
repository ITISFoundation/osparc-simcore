from ..errors import WebServerBaseError


class FoldersValueError(WebServerBaseError, ValueError):
    ...


class FolderValueNotPermittedError(FoldersValueError):
    msg_template = "Provided value is not permitted. {reason}"


class FolderNotFoundError(FoldersValueError):
    msg_template = "Folder not found. {reason}"


class FolderAccessForbiddenError(FoldersValueError):
    msg_template = "Folder access forbidden. {reason}"


class FolderGroupNotFoundError(FoldersValueError):
    msg_template = "Folder group not found. {reason}"
