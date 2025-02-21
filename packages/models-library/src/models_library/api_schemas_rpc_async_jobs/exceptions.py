from common_library.errors_classes import OsparcErrorMixin


class BaseAsyncjobRpcError(OsparcErrorMixin, RuntimeError):
    pass


class StatusError(BaseAsyncjobRpcError):
    msg_template: str = "Could not get status of job {job_id}"


class ResultError(BaseAsyncjobRpcError):
    msg_template: str = "Could not get results of job {job_id}"
