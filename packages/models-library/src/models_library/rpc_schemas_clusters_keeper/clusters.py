import datetime
from enum import auto

from pydantic import AnyUrl, BaseModel

from ..clusters import ClusterAuthentication
from ..users import UserID
from ..utils.enums import StrAutoEnum
from ..wallets import WalletID


class ClusterState(StrAutoEnum):
    STARTED = auto()
    RUNNING = auto()
    STOPPED = auto()


class OnDemandCluster(BaseModel):
    endpoint: AnyUrl
    authentication: ClusterAuthentication
    state: ClusterState
    user_id: UserID
    wallet_id: WalletID
    gateway_ready: bool
    eta: datetime.timedelta
