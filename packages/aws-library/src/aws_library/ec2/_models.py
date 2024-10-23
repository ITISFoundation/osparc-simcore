import datetime
import re
import tempfile
from dataclasses import dataclass
from typing import Annotated, Final, TypeAlias

import sh  # type: ignore[import-untyped]
from models_library.docker import DockerGenericTag
from pydantic import (
    BaseModel,
    ByteSize,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    StringConstraints,
    field_validator,
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
        return Resources.model_construct(
            **{
                key: a + b
                for (key, a), b in zip(
                    self.model_dump().items(), other.model_dump().values(), strict=True
                )
            }
        )

    def __sub__(self, other: "Resources") -> "Resources":
        return Resources.model_construct(
            **{
                key: a - b
                for (key, a), b in zip(
                    self.model_dump().items(), other.model_dump().values(), strict=True
                )
            }
        )

    @field_validator("cpus", mode="before")
    @classmethod
    def _floor_cpus_to_0(cls, v: float) -> float:
        return max(v, 0)


@dataclass(frozen=True, kw_only=True, slots=True)
class EC2InstanceType:
    name: InstanceTypeType
    resources: Resources


InstancePrivateDNSName: TypeAlias = str


AWS_TAG_KEY_MIN_LENGTH: Final[int] = 1
AWS_TAG_KEY_MAX_LENGTH: Final[int] = 128
AWSTagKey: TypeAlias = Annotated[
    # see [https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html#tag-restrictions]
    str,
    StringConstraints(
        min_length=AWS_TAG_KEY_MIN_LENGTH,
        max_length=AWS_TAG_KEY_MAX_LENGTH,
        pattern=re.compile(r"^(?!(_index|\.{1,2})$)[a-zA-Z0-9\+\-=\._:@]+$"),
    ),
]


AWS_TAG_VALUE_MIN_LENGTH: Final[int] = 0
AWS_TAG_VALUE_MAX_LENGTH: Final[int] = 256
AWSTagValue: TypeAlias = Annotated[
    # see [https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html#tag-restrictions]
    # quotes []{} were added as it allows to json encode. it seems to be accepted as a value
    str,
    StringConstraints(
        min_length=AWS_TAG_VALUE_MIN_LENGTH,
        max_length=AWS_TAG_VALUE_MAX_LENGTH,
        pattern=r"^[a-zA-Z0-9\s\+\-=\.,_:/@\"\'\[\]\{\}]*$",
    ),
]


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
    buffer_count: NonNegativeInt = Field(
        default=0, description="number of buffer EC2s to keep (defaults to 0)"
    )

    @field_validator("custom_boot_scripts")
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

    model_config = ConfigDict(
        json_schema_extra={
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
                {
                    # AMI + pre-pull + buffer count
                    "ami_id": "ami-123456789abcdef",
                    "pre_pull_images": [
                        "nginx:latest",
                        "itisfoundation/my-very-nice-service:latest",
                        "simcore/services/dynamic/another-nice-one:2.4.5",
                        "asd",
                    ],
                    "buffer_count": 10,
                },
            ]
        }
    )
