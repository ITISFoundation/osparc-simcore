from common_library.user_messages import user_message

from ..errors import WebServerBaseError


class StudyDispatcherError(WebServerBaseError, ValueError): ...


class IncompatibleServiceError(StudyDispatcherError):
    msg_template = user_message("None of the registered services can handle '{file_type}' files.", _version=1)


class FileToLargeError(StudyDispatcherError):
    msg_template = user_message("File size {file_size_in_mb} MB exceeds the allowed limit.", _version=1)


class ServiceNotFoundError(StudyDispatcherError):
    msg_template = user_message("Service {service_key}:{service_version} could not be found.", _version=1)


class InvalidRedirectionParamsError(StudyDispatcherError):
    msg_template = user_message("The provided link is invalid or incomplete.", _version=1)


class GuestUsersLimitError(StudyDispatcherError):
    msg_template = user_message(
        "Maximum number of guest users has been reached. Please log in with a registered account or try again later.",
        _version=1,
    )


class GuestUserNotAllowedError(StudyDispatcherError):
    msg_template = user_message("Guest users are not allowed to access this resource.", _version=1)


class ProjectWorkbenchMismatchError(StudyDispatcherError):
    msg_template = user_message(
        "Project {project_uuid} appears to be corrupted and cannot be accessed properly.",
        _version=1,
    )
