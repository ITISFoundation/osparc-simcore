import datetime
import re
import tempfile
from dataclasses import dataclass
from typing import Annotated, Final, TypeAlias

import sh  # type: ignore[import-untyped]
from common_library.basic_types import DEFAULT_FACTORY
from models_library.docker import DockerGenericTag
from pydantic import (
    BaseModel,
    ByteSize,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    StrictFloat,
    StrictInt,
    StringConstraints,
    field_validator,
)
from pydantic.config import JsonDict
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType

GenericResourceValue: TypeAlias = StrictInt | StrictFloat | str


class Resources(BaseModel, frozen=True):
    cpus: NonNegativeFloat
    ram: ByteSize
    generic_resources: Annotated[
        dict[str, GenericResourceValue],
        Field(
            default_factory=dict,
            description=(
                "Arbitrary additional resources (e.g. {'threads': 8}). "
                "Numeric values are treated as quantities and participate in add/sub/compare."
            ),
        ),
    ] = DEFAULT_FACTORY

    @classmethod
    def create_as_empty(cls) -> "Resources":
        return cls(cpus=0, ram=ByteSize(0))

    def __ge__(self, other: "Resources") -> bool:
        """operator for >= comparison
        if self has greater or equal resources than other, returns True
        Note that generic_resources are compared only if they are numeric
        Non-numeric generic resources must be equal in both or only defined in self
        to be considered greater or equal
        """

        if not (self.cpus >= other.cpus and self.ram >= other.ram):
            return False

        keys = set(self.generic_resources) | set(other.generic_resources)
        for k in keys:
            a = self.generic_resources.get(k)
            b = other.generic_resources.get(
                k, a
            )  # NOTE: get from other, default to "a" resources so that non-existing keys can be compared as equal
            if isinstance(a, int | float) and isinstance(b, int | float):
                if not (a >= b):
                    return False
            elif a != b:
                assert isinstance(a, str | None)  # nosec
                assert isinstance(b, int | float | str | None)  # nosec
                return False
        return True

    def __gt__(self, other: "Resources") -> bool:
        """operator for > comparison
        if self has greater resources than other, returns True
        Note that generic_resources are compared only if they are numeric
        Non-numeric generic resources must be equal in both or only defined in self
        to be considered greater
        """
        return self >= other and self != other

    def __add__(self, other: "Resources") -> "Resources":
        """operator for adding two Resources
        Note that only numeric generic resources are added
        Non-numeric generic resources are ignored
        """
        merged: dict[str, GenericResourceValue] = {}
        keys = set(self.generic_resources) | set(other.generic_resources)
        for k in keys:
            a = self.generic_resources.get(k)
            b = other.generic_resources.get(k)
            # adding non numeric values does not make sense, so we skip those for the resulting resource
            if isinstance(a, int | float) and isinstance(b, int | float):
                merged[k] = a + b
            elif a is None and isinstance(b, int | float):
                merged[k] = b
            elif b is None and isinstance(a, int | float):
                merged[k] = a

        return Resources.model_construct(
            cpus=self.cpus + other.cpus,
            ram=self.ram + other.ram,
            generic_resources=merged,
        )

    def __sub__(self, other: "Resources") -> "Resources":
        """operator for subtracting two Resources
        Note that only numeric generic resources are subtracted
        Non-numeric generic resources are ignored
        """
        merged: dict[str, GenericResourceValue] = {}
        keys = set(self.generic_resources) | set(other.generic_resources)
        for k in keys:
            a = self.generic_resources.get(k)
            b = other.generic_resources.get(k)
            # subtracting non numeric values does not make sense, so we skip those for the resulting resource
            if isinstance(a, int | float) and isinstance(b, int | float):
                merged[k] = a - b
            elif a is None and isinstance(b, int | float):
                merged[k] = -b
            elif b is None and isinstance(a, int | float):
                merged[k] = a

        return Resources.model_construct(
            cpus=self.cpus - other.cpus,
            ram=self.ram - other.ram,
            generic_resources=merged,
        )

    def __hash__(self) -> int:
        """Deterministic hash including cpus, ram (in bytes) and generic_resources."""
        # sort generic_resources items to ensure order-independent hashing
        generic_items: tuple[tuple[str, GenericResourceValue], ...] = tuple(
            sorted(self.generic_resources.items())
        )
        return hash((self.cpus, self.ram, generic_items))

    def as_flat_dict(self) -> dict[str, int | float | str]:
        """Like model_dump, but flattens generic_resources to top level keys"""
        base = self.model_dump()
        base.update(base.pop("generic_resources"))
        return base

    @classmethod
    def from_flat_dict(cls, data: dict[str, int | float | str]) -> "Resources":
        """Inverse of as_flat_dict"""
        generic_resources = {k: v for k, v in data.items() if k not in {"cpus", "ram"}}
        return cls(
            cpus=float(data.get("cpus", 0)),
            ram=ByteSize(data.get("ram", 0)),
            generic_resources=generic_resources,
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
    subnet_ids: list[str]
    iam_instance_profile: str


AMIIdStr: TypeAlias = str
CommandStr: TypeAlias = str


class EC2InstanceBootSpecific(BaseModel):
    ami_id: AMIIdStr
    custom_boot_scripts: Annotated[
        list[CommandStr],
        Field(
            default_factory=list,
            description="script(s) to run on EC2 instance startup (be careful!), "
            "each entry is run one after the other using '&&' operator",
        ),
    ] = DEFAULT_FACTORY
    pre_pull_images: Annotated[
        list[DockerGenericTag],
        Field(
            default_factory=list,
            description="a list of docker image/tags to pull on the instance",
        ),
    ] = DEFAULT_FACTORY
    buffer_count: Annotated[
        NonNegativeInt,
        Field(description="number of buffer EC2s to keep (defaults to 0)"),
    ] = 0

    @field_validator("custom_boot_scripts")
    @classmethod
    def validate_bash_calls(cls, v):
        try:
            with tempfile.NamedTemporaryFile(mode="wt", delete=True) as temp_file:
                temp_file.writelines(v)
                temp_file.flush()
                # NOTE: this will not capture runtime errors, but at least some syntax errors such as invalid quotes
                sh.bash(
                    "-n",
                    temp_file.name,  # pyright: ignore[reportCallIssue]
                )  # sh is untyped, but this call is safe for bash syntax checking
        except sh.ErrorReturnCode as exc:
            msg = f"Invalid bash call in custom_boot_scripts: {v}, Error: {exc.stderr}"
            raise ValueError(msg) from exc

        return v

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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
                        "pre_pull_images_cron_interval": "01:00:00",  # retired but kept for tests
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

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )
