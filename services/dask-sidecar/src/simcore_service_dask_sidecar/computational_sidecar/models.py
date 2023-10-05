import re

from models_library.basic_types import VERSION_RE
from models_library.services import ServiceDockerData
from packaging import version
from pydantic import BaseModel, ByteSize, Extra, Field, validator

LEGACY_INTEGRATION_VERSION = version.Version("0")
PROGRESS_REGEXP: re.Pattern[str] = re.compile(
    r"^(?:\[?PROGRESS\]?:?)?\s*"
    r"(?P<value>[0-1]?\.\d+|"
    r"\d+\s*(?:(?P<percent_sign>%)|"
    r"\d+\s*"
    r"(?P<percent_explicit>percent))|"
    r"\[?(?P<fraction>\d+\/\d+)\]?"
    r"|0|1)"
)


class ContainerHostConfig(BaseModel):
    # NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/3506
    # Be careful! --priviledged, --pid=host --cap-add XXX should never be usable here!!
    # at the moment they are not part of the possible configuration but if they were
    # to, ensure they are properly validated

    binds: list[str] = Field(
        ..., alias="Binds", description="A list of volume bindings for this container"
    )
    init: bool = Field(
        default=True,
        alias="Init",
        description="Run an init inside the container that forwards signals and reaps processes. This field is omitted if empty, and the default (as configured on the daemon) is used",
    )
    memory: ByteSize = Field(..., alias="Memory", description="Memory limit in bytes")
    memory_swap: ByteSize | None = Field(
        default=None,
        alias="MemorySwap",
        description="Total memory limit (memory + swap). Set as -1 to enable unlimited swap.",
    )
    nano_cpus: int = Field(
        ..., alias="NanoCPUs", description="CPU quota in units of 10-9 CPUs"
    )

    @validator("memory_swap", pre=True, always=True)
    @classmethod
    def ensure_no_memory_swap_means_no_swap(cls, v, values):
        if v is None:
            # if not set it will be the same value as memory to ensure swap is disabled
            return values["memory"]
        return v

    @validator("memory_swap")
    @classmethod
    def ensure_memory_swap_cannot_be_unlimited_nor_smaller_than_memory(cls, v, values):
        if v < values["memory"]:
            msg = "Memory swap cannot be set to a smaller value than memory"
            raise ValueError(msg)
        return v


class DockerContainerConfig(BaseModel):
    env: list[str] = Field(..., alias="Env")
    cmd: list[str] = Field(..., alias="Cmd")
    image: str = Field(..., alias="Image")
    labels: dict[str, str] = Field(..., alias="Labels")
    host_config: ContainerHostConfig = Field(..., alias="HostConfig")


class ImageLabels(BaseModel):
    integration_version: str = Field(
        default=str(LEGACY_INTEGRATION_VERSION),
        alias="integration-version",
        description="integration version number",
        regex=VERSION_RE,
        examples=["1.0.0"],
    )
    progress_regexp: str = Field(
        default=PROGRESS_REGEXP.pattern,
        alias="progress_regexp",
        description="regexp pattern for detecting computational service's progress",
    )

    class Config:
        extra = Extra.ignore

    @validator("integration_version", pre=True)
    @classmethod
    def default_integration_version(cls, v):
        if v is None:
            return ImageLabels().integration_version
        return v

    @validator("progress_regexp", pre=True)
    @classmethod
    def default_progress_regexp(cls, v):
        if v is None:
            return ImageLabels().progress_regexp
        return v

    def get_integration_version(self) -> version.Version:
        return version.Version(self.integration_version)

    def get_progress_regexp(self) -> re.Pattern[str]:
        return re.compile(self.progress_regexp)


assert set(ImageLabels.__fields__).issubset(
    ServiceDockerData.__fields__
), "ImageLabels must be compatible with ServiceDockerData"
