from pydantic import BaseModel

from ..wallets import WalletID


class WalletTotalCredits(BaseModel):
    wallet_id: WalletID
    available_credits: float
