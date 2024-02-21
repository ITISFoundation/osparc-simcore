from ..errors import WebServerBaseError


class WalletsValueError(WebServerBaseError, ValueError):
    ...


class WalletNotFoundError(WalletsValueError):
    msg_template = "Wallet not found. {reason}"


class WalletAccessForbiddenError(WalletsValueError):
    msg_template = "Wallet access forbidden. {reason}"


class WalletNotEnoughCreditsError(WalletsValueError):
    msg_template = "Wallet does not have enough credits. {reason}"


# Wallet groups


class WalletGroupNotFoundError(WalletsValueError):
    msg_template = "Wallet group not found. {reason}"
