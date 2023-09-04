import datetime
from dataclasses import dataclass
from enum import auto
from typing import TypeAlias

from models_library.clusters import ClusterAuthentication, SimpleAuthentication
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
from models_library.wallets import WalletID
from pydantic import AnyUrl, BaseModel, ByteSize, PositiveInt, SecretStr, parse_obj_as
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


@dataclass(frozen=True)
class EC2InstanceType:
    name: str
    cpus: PositiveInt
    ram: ByteSize


InstancePrivateDNSName = str
EC2Tags: TypeAlias = dict[str, str]


@dataclass(frozen=True)
class EC2InstanceData:
    launch_time: datetime.datetime
    id: str  # noqa: A003
    aws_private_dns: InstancePrivateDNSName
    aws_public_ip: str | None
    type: InstanceTypeType  # noqa: A003
    state: InstanceStateNameType
    tags: EC2Tags


class ClusterState(StrAutoEnum):
    STARTED = auto()
    RUNNING = auto()
    STOPPED = auto()


def _convert_ec2_state_to_cluster_state(
    ec2_state: InstanceStateNameType,
) -> ClusterState:
    match ec2_state:
        case "pending":
            return ClusterState.STARTED  # type: ignore
        case "running":
            return ClusterState.RUNNING  # type: ignore
        case _:
            return ClusterState.STOPPED  # type: ignore


class ClusterGet(BaseModel):
    endpoint: AnyUrl
    authentication: ClusterAuthentication
    state: ClusterState
    user_id: UserID
    wallet_id: WalletID
    gateway_ready: bool = False

    @classmethod
    def from_ec2_instance_data(
        cls,
        instance: EC2InstanceData,
        user_id: UserID,
        wallet_id: WalletID,
        gateway_password: SecretStr,
    ) -> "ClusterGet":
        return cls(
            endpoint=parse_obj_as(AnyUrl, f"http://{instance.aws_public_ip}"),
            authentication=SimpleAuthentication(
                username=f"{user_id}", password=gateway_password
            ),
            state=_convert_ec2_state_to_cluster_state(instance.state),
            user_id=user_id,
            wallet_id=wallet_id,
        )
