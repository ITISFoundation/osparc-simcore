from common_library.user_messages import user_message

from ._base import ApiServerBaseError


class CustomBaseError(ApiServerBaseError):
    pass


class InsufficientCreditsError(CustomBaseError):
    # NOTE: Same message as WalletNotEnoughCreditsError
    msg_template = user_message(
        "Wallet '{wallet_name}' has {wallet_credit_amount} credits. Please add credits before requesting solver outputs.",
        _version=1,
    )


class MissingWalletError(CustomBaseError):
    msg_template = user_message(
        "Job {job_id} does not have an associated wallet.", _version=1
    )


class ApplicationSetupError(CustomBaseError):
    pass


class ServiceConfigurationError(CustomBaseError, ValueError):
    msg_template = "{service_cls_name} invalid configuration: {detail_msg}."


class SolverServiceListJobsFiltersError(
    ServiceConfigurationError
):  # pylint: disable=too-many-ancestors
    service_cls_name = "SolverService"
    detail_msg = user_message(
        "The solver_version parameter is set but solver_id is not. Please provide both parameters or neither.",
        _version=1,
    )
