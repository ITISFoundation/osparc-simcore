from ..errors import WebServerBaseError


class WalletsValueError(WebServerBaseError, ValueError): ...


class WalletNotFoundError(WalletsValueError):
    msg_template = "Wallet not found: {details}"


class WalletAccessForbiddenError(WalletsValueError):
    msg_template = "Wallet access forbidden: {details}"


class WalletNotEnoughCreditsError(WalletsValueError):
    msg_template = "Wallet does not have enough credits: {details}"


# Wallet groups


class WalletGroupNotFoundError(WalletsValueError):
    msg_template = "Wallet group not found: {details}"
