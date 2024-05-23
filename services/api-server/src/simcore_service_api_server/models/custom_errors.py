from .errors import ApiServerBaseError


class CustomBaseError(ApiServerBaseError):
    pass


class InsufficientCreditsError(CustomBaseError):
    pass


class MissingWalletError(CustomBaseError):
    pass


class ApplicationSetupError(CustomBaseError):
    pass
