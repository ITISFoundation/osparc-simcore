"""Defines the different exceptions that may arise in the wallets subpackage"""
from models_library.users import GroupID
from models_library.wallets import WalletID


class WalletsException(Exception):
    """Basic exception for errors raised in wallets"""

    def __init__(self, msg: str | None = None):
        super().__init__(msg or "Unexpected error occured in wallets subpackage")


class WalletNotFoundError(WalletsException):
    def __init__(self, *, wallet_id: WalletID):
        super().__init__(f"Wallet id {wallet_id} not found")
        self.wallet_id = wallet_id


class WalletAccessForbiddenError(WalletsException):
    def __init__(self, *, wallet_id: WalletID):
        super().__init__(f"User does not have access to wallet id {wallet_id}")
        self.wallet_id = wallet_id


### Wallet Groups


class WalletGroupNotFoundError(WalletsException):
    def __init__(self, *, wallet_id: WalletID, group_id: GroupID):
        super().__init__(f"Group id {group_id} for wallet id {wallet_id} not found")
        self.wallet_id = wallet_id
        self.group_id = group_id
