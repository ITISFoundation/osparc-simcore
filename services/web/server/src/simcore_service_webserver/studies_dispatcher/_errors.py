from pydantic.errors import PydanticErrorMixin


class StudyDispatcherError(ValueError):
    ...


class IncompatibleService(PydanticErrorMixin, StudyDispatcherError):
    code = "studies_dispatcher.incompatible_service"
    msg_template = "None of the registered services can handle '{file_type}'"


class FileToLarge(PydanticErrorMixin, StudyDispatcherError):
    code = "studies_dispatcher.file_to_large"
    msg_template = "File size {file_size_in_mb} MB is over allowed limit"


class ServiceNotFound(PydanticErrorMixin, StudyDispatcherError):
    code = "studies_dispatcher.service_not_found"
    msg_template = "Service {service_key}:{service_version} not found"


class InvalidRedirectionParams(PydanticErrorMixin, StudyDispatcherError):
    code = "studies_dispatcher.invalid_redirection_params"
    msg_template = (
        "Invalid request link: cannot find any reference to either data or a service"
    )
