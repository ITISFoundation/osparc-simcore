import pathlib
from typing import Any, Dict, Optional

import pydantic.json
from models_library.service_settings_labels import (
    PathMappingsLabel,
    SimcoreServiceSettingsLabel,
)
from models_library.services import ServiceDockerData
from pydantic.main import BaseModel, Extra

pydantic.json.ENCODERS_BY_TYPE[pathlib.PosixPath] = str
pydantic.json.ENCODERS_BY_TYPE[pathlib.WindowsPath] = str


OSPARC_LABEL_PREFIXES = ("io.simcore", "simcore.service", "io.osparc", "swiss.z43")
# FIXME: all to swiss.z43 or to io.osparc


# https://github.com/compose-spec/compose-spec/blob/master/spec.md
ComposeSpec = Dict[str, Any]


class OsparcServiceSpecs(ServiceDockerData):
    compose_spec: Optional[ComposeSpec]
    container_http_entrypoint: Optional[str]

    paths_mapping: PathMappingsLabel

    settings: SimcoreServiceSettingsLabel

    class Config:
        alias_generator = lambda field_name: field_name.replace("_", "-")
        allow_population_by_field_name = True
        extra = Extra.forbid

    def to_labels_annotations(self) -> Dict[str, str]:
        labels = {}
        for key, value in self.dict(
            exclude_unset=True, by_alias=True, exclude_none=True
        ).items():

            if isinstance(value, BaseModel):
                if key == "paths-mapping":
                    import pdb

                    pdb.set_trace()
                value = value.json(exclude_unset=True, by_alias=True, exclude_none=True)

            if key in ServiceDockerData.__fields__:
                labels[f"{OSPARC_LABEL_PREFIXES[0]}.{key}"] = f"{value}"
            else:
                labels[f"{OSPARC_LABEL_PREFIXES[1]}.{key}"] = f"{value}"

        return labels

    @classmethod
    def from_labels_annotations(cls, labels: Dict[str, str]) -> "OsparcServiceSpecs":
        raise NotImplementedError
