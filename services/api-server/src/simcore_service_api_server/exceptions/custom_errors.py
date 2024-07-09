from ._base import ApiServerBaseError


class CustomBaseError(ApiServerBaseError):
    pass


class InsufficientCreditsError(CustomBaseError):
    # NOTE: Same message as WalletNotEnoughCreditsError
    msg_template = "Wallet '{wallet_name}' has {wallet_credit_amount} credits. Please add some before requesting solver ouputs"


class MissingWalletError(CustomBaseError):
    msg_template = "Job {job_id} does not have an associated wallet."


class ApplicationSetupError(CustomBaseError):
    pass
