import datetime
from dataclasses import dataclass
from enum import auto

from pydantic import AnyUrl, BaseModel, ByteSize, PositiveInt

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
    wallet_id: WalletID | None
    dask_scheduler_ready: bool
    eta: datetime.timedelta


@dataclass(frozen=True)
class EC2InstanceType:
    name: str
    cpus: PositiveInt
    ram: ByteSize
