from common_library.errors_classes import OsparcErrorMixin


class BaseAsyncjobRpcError(OsparcErrorMixin, RuntimeError):
    pass


class JobSchedulerError(BaseAsyncjobRpcError):
    msg_template: str = "Async job scheduler exception: {exc}"


class JobMissingError(BaseAsyncjobRpcError):
    msg_template: str = "Job {job_id} does not exist"


class JobStatusError(BaseAsyncjobRpcError):
    msg_template: str = "Could not get status of job {job_id}"


class JobNotDoneError(BaseAsyncjobRpcError):
    msg_template: str = "Job {job_id} not done"


class JobAbortedError(BaseAsyncjobRpcError):
    msg_template: str = "Job {job_id} aborted"


class JobError(BaseAsyncjobRpcError):
    msg_template: str = (
        "Job '{job_id}' failed with exception type '{exc_type}' and message: {exc_msg}"
    )
