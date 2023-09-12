from decimal import Decimal

from pydantic import BaseModel, validator

from ..wallets import WalletID


class WalletTotalCredits(BaseModel):
    wallet_id: WalletID
    available_osparc_credits: Decimal

    @validator("available_osparc_credits", always=True)
    @classmethod
    def ensure_rounded(cls, v):
        return round(v, 2)
