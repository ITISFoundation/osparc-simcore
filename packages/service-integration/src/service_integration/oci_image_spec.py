""" Support for Open Container Initiative (OCI)

SEE https://opencontainers.org
SEE https://github.com/opencontainers
SEE https://github.com/opencontainers/image-spec/blob/main/annotations.md
"""

import os
from datetime import datetime
from typing import Dict

from models_library.basic_types import SHA1Str, VersionStr
from pydantic import BaseModel, Field
from pydantic.main import Extra
from pydantic.networks import AnyUrl

#
# Prefix added to docker image labels using reverse DNS notations of a domain they own
# SEE https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
#
DOCKER_LABEL_PREFIXES = ("com.docker", "io.docker", "org.dockerproject")
LS_LABEL_PREFIX = "org.label-schema"
OCI_LABEL_PREFIX = "org.opencontainers.image"


class LabelSchemaAnnotations(BaseModel):
    """
    NOTE:  DEPRECATED IN FAVOUR OF OCI IMAGE SPEC
    """

    schema_version: VersionStr = Field("1.0", alias="schema-version")

    build_date: datetime
    vcs_ref: str
    vcs_url: AnyUrl

    class Config:
        alias_generator = lambda field_name: field_name.replace("_", "-")
        allow_population_by_field_name = True
        extra = Extra.forbid

    @classmethod
    def create_from_env(cls) -> "LabelSchemaAnnotations":
        data = {}
        for field_name in cls.__fields__:
            if value := os.environ.get(field_name.upper()):
                data[field_name] = value
        return cls(**data)


class OCIImageSpecAnnotations(BaseModel):

    created: datetime = Field(
        ...,
        description="date and time on which the image was built (string, date-time as defined by RFC 3339)",
    )

    authors: str = Field(
        ...,
        description="contact details of the people or organization responsible for the image (freeform string)",
    )
    url: AnyUrl = Field(
        ..., description="URL to find more information on the image (string)"
    )
    documentation: AnyUrl = Field(
        ..., description="URL to get documentation on the image (string)"
    )
    source: AnyUrl = Field(
        ..., description="URL to get source code for building the image (string)"
    )
    version: VersionStr = Field(
        ...,
        description="version of the packaged software"
        "The version MAY match a label or tag in the source code repository"
        "version MAY be Semantic versioning-compatible",
    )
    revision: str = Field(
        ..., description="Source control revision identifier for the packaged software."
    )
    vendor: str = Field(
        ..., description="Name of the distributing entity, organization or individual."
    )
    # SEE https://spdx.dev/spdx-specification-21-web-version/#h.jxpfx0ykyb60
    licenses: str = Field(
        "MIT",
        description="License(s) under which contained software is distributed as an SPDX License Expression.",
    )
    ref_name: str = Field(
        None,
        description="Name of the reference for a target (string).",
    )

    title: str = Field(..., description="Human-readable title of the image (string)")
    description: str = Field(
        ...,
        description="Human-readable description of the software packaged in the image (string)",
    )
    base_digest: SHA1Str = Field(
        ...,
        description="Digest of the image this image is based on (string)",
    )

    class Config:
        alias_generator = lambda field_name: field_name.replace("_", ".")
        allow_population_by_field_name = True
        extra = Extra.forbid

    def to_labels_annotations(self) -> Dict[str, str]:
        return {
            f"{OCI_LABEL_PREFIX}.{key}": f"{value}"
            for key, value in self.dict(
                exclude_unset=True, by_alias=True, exclude_none=True
            ).items()
        }

    def from_labels_annotations(self, annotations: Dict[str, str]):
        raise NotImplementedError


def convert_from_label_schema_annotations():
    """label-schema has be deprecated in favor of OCI image specs

    See conversion rules https://github.com/opencontainers/image-spec/blob/main/annotations.md#back-compatibility-with-label-schema
    """
    raise NotImplementedError
