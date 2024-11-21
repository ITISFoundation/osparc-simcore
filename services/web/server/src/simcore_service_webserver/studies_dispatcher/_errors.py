from ..errors import WebServerBaseError


class StudyDispatcherError(WebServerBaseError, ValueError):
    ...


class IncompatibleService(StudyDispatcherError):
    msg_template = "None of the registered services can handle '{file_type}'"


class FileToLarge(StudyDispatcherError):
    msg_template = "File size {file_size_in_mb} MB is over allowed limit"


class ServiceNotFound(StudyDispatcherError):
    msg_template = "Service {service_key}:{service_version} not found"


class InvalidRedirectionParams(StudyDispatcherError):
    msg_template = (
        "The link you provided is invalid because it doesn't contain any information related to data or a service."
        " Please check the link and make sure it is correct."
    )


class GuestUsersLimitError(StudyDispatcherError):
    msg_template = "Maximum number of guests was reached. Please login with a registered user or try again later"
