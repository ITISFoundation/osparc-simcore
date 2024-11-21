import datetime
from enum import auto

from pydantic import AnyUrl, BaseModel, Field

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
    authentication: ClusterAuthentication = Field(discriminator="type")
    state: ClusterState
    user_id: UserID
    wallet_id: WalletID | None
    dask_scheduler_ready: bool
    eta: datetime.timedelta
