"""Request/response schemas for wallets handlers."""

from models_library.groups import GroupID
from models_library.rest_base import StrictRequestParameters
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict


class WalletsPathParams(StrictRequestParameters):
    wallet_id: WalletID


class _WalletsGroupsPathParams(BaseModel):
    wallet_id: WalletID
    group_id: GroupID
    model_config = ConfigDict(extra="forbid")


class _WalletsGroupsBodyParams(BaseModel):
    read: bool
    write: bool
    delete: bool
    model_config = ConfigDict(extra="forbid")
