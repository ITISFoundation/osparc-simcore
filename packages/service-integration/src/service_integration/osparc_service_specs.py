#
# osparc user's service specifications
#
# TODO: distinguish betweeen image_spec and run_spec
#

from pathlib import Path
from typing import Any, Dict, List, Optional

from models_library.services import ServiceDockerData
from pydantic.fields import Field
from pydantic.main import BaseModel, Extra

from .compose_spec_model import ComposeSpecification

# pydantic.json.ENCODERS_BY_TYPE[pathlib.PosixPath] = str
# pydantic.json.ENCODERS_BY_TYPE[pathlib.WindowsPath] = str


OSPARC_LABEL_PREFIXES = ("io.simcore", "simcore.service", "io.osparc", "swiss.z43")
# FIXME: all to swiss.z43 or to io.osparc


MetaSpecification = ServiceDockerData


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
    stype: str = Field(
        ...,
        description="The type of the service setting (follows Docker REST API naming scheme)",
        alias="type",
    )
    value: Any = Field(
        ...,
        description="The value of the service setting (shall follow Docker REST API scheme for services",
    )


class OsparcServiceSpecification(MetaSpecification):
    compose_spec: Optional[ComposeSpecification] = None
    container_http_entrypoint: Optional[str] = None

    paths_mapping: Optional[PathsMapping] = None

    settings: List[SettingsItem] = []

    class Config:
        alias_generator = lambda field_name: field_name.replace("_", "-")
        allow_population_by_field_name = True
        extra = Extra.forbid

    # NOTE: data is load/dump from/to image labels annotations
    def to_labels_annotations(self) -> Dict[str, str]:
        labels = {}
        for key, value in self.dict(
            exclude_unset=True, by_alias=True, exclude_none=True
        ).items():

            if isinstance(value, BaseModel):
                if key == "paths-mapping":
                    value = value.json(
                        exclude_unset=True, by_alias=True, exclude_none=True
                    )

            if key in MetaSpecification.__fields__:
                labels[f"{OSPARC_LABEL_PREFIXES[0]}.{key}"] = f"{value}"
            else:
                labels[f"{OSPARC_LABEL_PREFIXES[1]}.{key}"] = f"{value}"

        return labels

    @classmethod
    def from_labels_annotations(cls, labels: Dict[str, str]) -> "ServiceSpecification":
        raise NotImplementedError
