import datetime
import re
import tempfile
from dataclasses import dataclass
from typing import Any, ClassVar, TypeAlias

import sh
from models_library.docker import DockerGenericTag
from pydantic import (
    BaseModel,
    ByteSize,
    ConstrainedStr,
    Extra,
    Field,
    NonNegativeFloat,
    validator,
)
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType


class Resources(BaseModel, frozen=True):
    cpus: NonNegativeFloat
    ram: ByteSize

    @classmethod
    def create_as_empty(cls) -> "Resources":
        return cls(cpus=0, ram=ByteSize(0))

    def __ge__(self, other: "Resources") -> bool:
        return self.cpus >= other.cpus and self.ram >= other.ram

    def __gt__(self, other: "Resources") -> bool:
        return self.cpus > other.cpus or self.ram > other.ram

    def __add__(self, other: "Resources") -> "Resources":
        return Resources.construct(
            **{
                key: a + b
                for (key, a), b in zip(
                    self.dict().items(), other.dict().values(), strict=True
                )
            }
        )

    def __sub__(self, other: "Resources") -> "Resources":
        return Resources.construct(
            **{
                key: a - b
                for (key, a), b in zip(
                    self.dict().items(), other.dict().values(), strict=True
                )
            }
        )

    @validator("cpus", pre=True)
    @classmethod
    def _floor_cpus_to_0(cls, v: float) -> float:
        return max(v, 0)


@dataclass(frozen=True, kw_only=True, slots=True)
class EC2InstanceType:
    name: InstanceTypeType
    resources: Resources


InstancePrivateDNSName: TypeAlias = str


class AWSTagKey(ConstrainedStr):
    # see [https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html#tag-restrictions]
    regex = re.compile(r"^(?!(_index|\.{1,2})$)[a-zA-Z0-9\+\-=\._:@]{1,128}$")


class AWSTagValue(ConstrainedStr):
    # see [https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html#tag-restrictions]
    # quotes []{} were added as it allows to json encode. it seems to be accepted as a value
    regex = re.compile(r"^[a-zA-Z0-9\s\+\-=\.,_:/@\"\'\[\]\{\}]{0,256}$")


EC2Tags: TypeAlias = dict[AWSTagKey, AWSTagValue]


@dataclass(frozen=True)
class EC2InstanceData:
    launch_time: datetime.datetime
    id: str
    aws_private_dns: InstancePrivateDNSName
    aws_public_ip: str | None
    type: InstanceTypeType
    state: InstanceStateNameType
    resources: Resources
    tags: EC2Tags

    def __hash__(self) -> int:
        return hash(
            (
                self.launch_time,
                self.id,
                self.aws_private_dns,
                self.aws_public_ip,
                self.type,
                self.state,
                self.resources,
                tuple(sorted(self.tags.items())),
            )
        )


@dataclass(frozen=True)
class EC2InstanceConfig:
    type: EC2InstanceType
    tags: EC2Tags
    startup_script: str

    ami_id: str
    key_name: str
    security_group_ids: list[str]
    subnet_id: str
    iam_instance_profile: str


AMIIdStr: TypeAlias = str
CommandStr: TypeAlias = str


class EC2InstanceBootSpecific(BaseModel):
    ami_id: AMIIdStr
    custom_boot_scripts: list[CommandStr] = Field(
        default_factory=list,
        description="script(s) to run on EC2 instance startup (be careful!), "
        "each entry is run one after the other using '&&' operator",
    )
    pre_pull_images: list[DockerGenericTag] = Field(
        default_factory=list,
        description="a list of docker image/tags to pull on instance cold start",
    )
    pre_pull_images_cron_interval: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=30),
        description="time interval between pulls of images (minimum is 1 minute) "
        "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    # just AMI
                    "ami_id": "ami-123456789abcdef",
                },
                {
                    # AMI + scripts
                    "ami_id": "ami-123456789abcdef",
                    "custom_boot_scripts": ["ls -tlah", "echo blahblah"],
                },
                {
                    # AMI + scripts + pre-pull
                    "ami_id": "ami-123456789abcdef",
                    "custom_boot_scripts": ["ls -tlah", "echo blahblah"],
                    "pre_pull_images": [
                        "nginx:latest",
                        "itisfoundation/my-very-nice-service:latest",
                        "simcore/services/dynamic/another-nice-one:2.4.5",
                        "asd",
                    ],
                },
                {
                    # AMI + pre-pull
                    "ami_id": "ami-123456789abcdef",
                    "pre_pull_images": [
                        "nginx:latest",
                        "itisfoundation/my-very-nice-service:latest",
                        "simcore/services/dynamic/another-nice-one:2.4.5",
                        "asd",
                    ],
                },
                {
                    # AMI + pre-pull + cron
                    "ami_id": "ami-123456789abcdef",
                    "pre_pull_images": [
                        "nginx:latest",
                        "itisfoundation/my-very-nice-service:latest",
                        "simcore/services/dynamic/another-nice-one:2.4.5",
                        "asd",
                    ],
                    "pre_pull_images_cron_interval": "01:00:00",
                },
            ]
        }

    @validator("custom_boot_scripts")
    @classmethod
    def validate_bash_calls(cls, v):
        try:
            with tempfile.NamedTemporaryFile(mode="wt", delete=True) as temp_file:
                temp_file.writelines(v)
                temp_file.flush()
                # NOTE: this will not capture runtime errors, but at least some syntax errors such as invalid quotes
                sh.bash("-n", temp_file.name)
        except sh.ErrorReturnCode as exc:
            msg = f"Invalid bash call in custom_boot_scripts: {v}, Error: {exc.stderr}"
            raise ValueError(msg) from exc

        return v
