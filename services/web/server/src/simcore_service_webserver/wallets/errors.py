"""
    API plugin errors
"""


from pydantic.errors import PydanticErrorMixin


class WalletsErrors(PydanticErrorMixin, ValueError):
    ...


class WalletNotFoundError(WalletsErrors):
    msg_template = "Wallet not found. {reason}"


class WalletAccessForbiddenError(WalletsErrors):
    msg_template = "Wallet access forbidden. {reason}"


# Wallet groups


class WalletGroupNotFoundError(WalletsErrors):
    msg_template = "Wallet group not found. {reason}"
