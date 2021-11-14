""" Defines the configuration of a user service stored in '.osparc/' folder

    - models for config sections
        - load/dump from/to yaml
        - load/save from label annotations
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from models_library.services import (
    COMPUTATIONAL_SERVICE_KEY_FORMAT,
    DYNAMIC_SERVICE_KEY_FORMAT,
    ServiceDockerData,
    ServiceType,
)
from pydantic.fields import Field
from pydantic.main import BaseModel, Extra

from .compose_spec_model import ComposeSpecification
from .labels_annotations import to_labels
from .yaml_utils import yaml_safe_load

CONFIG_FOLDER_NAME = ".osparc"


REGISTRY_PREFIX = {
    "local": "registry:5000",
    "dockerhub": "itisfoundation",
}
# TODO: read from config all available registries

SERVICE_KEY_FORMATS = {
    ServiceType.COMPUTATIONAL: COMPUTATIONAL_SERVICE_KEY_FORMAT,
    ServiceType.DYNAMIC: DYNAMIC_SERVICE_KEY_FORMAT,
}

OSPARC_LABEL_PREFIXES = ("io.simcore", "simcore.service", "io.osparc", "swiss.z43")
# FIXME: all to swiss.z43 or to io.osparc


## MODELS -------------------------


class IOSpecification(ServiceDockerData):
    """General info + I/O specs

    Include both image and runtime specs
    """

    @classmethod
    def from_yaml(cls, path: Path) -> "IOSpecification":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        return cls.parse_obj(data)

    def to_labels_annotations(self) -> Dict[str, str]:
        io_labels = to_labels(
            self.dict(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[0],
            trim_key_head=False,
        )
        return io_labels

    def image_name(self, registry="local") -> str:
        registry_prefix = REGISTRY_PREFIX[registry]
        mid_name = SERVICE_KEY_FORMATS[self.service_type].format(service_name=self.name)
        if registry in "dockerhub":
            # dockerhub allows only one-level names -> dot it
            # TODO: check thisname is compatible with REGEX
            mid_name = mid_name.replace("/", ".")

        tag = self.version
        return f"{registry_prefix}/{mid_name}:{tag}"


class PathsMapping(BaseModel):
    inputs_path: Path = Field(
        ..., description="folder path where the service expects all the inputs"
    )
    outputs_path: Path = Field(
        ...,
        description="folder path where the service is expected to provide all its outputs",
    )
    state_paths: List[Path] = Field(
        [],
        description="optional list of paths which contents need to be persisted",
    )

    class Config:
        schema_extra = {
            "example": {
                "outputs_path": "/outputs",
                "inputs_path": "/inputs",
                "state_paths": ["/workdir1", "/workdir2"],
            }
        }


class SettingsItem(BaseModel):
    name: str = Field(..., description="The name of the service setting")
    type_: str = Field(
        ...,
        description="The type of the service setting (follows Docker REST API naming scheme)",
        alias="type",
    )
    value: Any = Field(
        ...,
        description="The value of the service setting (shall follow Docker REST API scheme for services",
    )


class ServiceSpecification(BaseModel):
    """Runtime specs"""

    compose_spec: Optional[ComposeSpecification] = None
    container_http_entrypoint: Optional[str] = None

    paths_mapping: Optional[PathsMapping] = None

    settings: List[SettingsItem] = []

    class Config:
        alias_generator = lambda field_name: field_name.replace("_", "-")
        allow_population_by_field_name = True
        extra = Extra.forbid

    @classmethod
    def from_yaml(cls, path: Path) -> "ServiceSpecification":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        return cls.parse_obj(data)

    # NOTE: data is load/dump from/to image labels annotations
    def to_labels_annotations(self) -> Dict[str, str]:
        service_labels = to_labels(
            self.dict(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[1],
        )
        return service_labels

    @classmethod
    def from_labels_annotations(cls, labels: Dict[str, str]) -> "ServiceSpecification":
        raise NotImplementedError
