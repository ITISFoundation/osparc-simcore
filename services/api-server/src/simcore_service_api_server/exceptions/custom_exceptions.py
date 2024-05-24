from .base_exceptions import ApiServerBaseError


class CustomBaseError(ApiServerBaseError):
    pass


class InsufficientCreditsError(CustomBaseError):
    msg_template = "Wallet '{wallet_name}' does not have any credits. Please add some before requesting solver ouputs"


class MissingWalletError(CustomBaseError):
    msg_template = "Job {job_id} does not have an associated wallet."


class ApplicationSetupError(CustomBaseError):
    pass
