""" Support for Open Container Initiative (OCI)

SEE https://opencontainers.org
SEE https://github.com/opencontainers
SEE https://github.com/opencontainers/image-spec/blob/main/annotations.md
"""

import os
from datetime import datetime
from typing import Any, Dict

from models_library.basic_types import SHA1Str, VersionStr
from pydantic import BaseModel, Field
from pydantic.main import Extra
from pydantic.networks import AnyUrl

from .labels_annotations import from_labels, to_labels

#
# Prefix added to docker image labels using reverse DNS notations of a domain they own
# SEE https://docs.docker.com/config/labels-custom-metadata/#key-format-recommendations
#
DOCKER_LABEL_PREFIXES = ("com.docker", "io.docker", "org.dockerproject")
LS_LABEL_PREFIX = "org.label-schema"
OCI_LABEL_PREFIX = "org.opencontainers.image"

# See conversion rules https://github.com/opencontainers/image-spec/blob/main/annotations.md#back-compatibility-with-label-schema
_TO_OCI = {
    "build-date": "created",
    "url": "url",
    "vcs-url": "source",
    "version": "version",
    "vcs-ref": "revision",
    "vendor": "vendor",
    "name": "title",
    "description": "descripton",
    "usage": "documentation",
}


class OciImageSpecAnnotations(BaseModel):
    # TODO: review and polish constraints

    created: datetime = Field(
        None,
        description="date and time on which the image was built (string, date-time as defined by RFC 3339)",
    )

    authors: str = Field(
        None,
        description="contact details of the people or organization responsible for the image (freeform string)",
    )

    url: AnyUrl = Field(
        None, description="URL to find more information on the image (string)"
    )

    documentation: AnyUrl = Field(
        None, description="URL to get documentation on the image (string)"
    )

    source: AnyUrl = Field(
        None, description="URL to get source code for building the image (string)"
    )

    version: VersionStr = Field(
        None,
        description="version of the packaged software"
        "The version MAY match a label or tag in the source code repository"
        "version MAY be Semantic versioning-compatible",
    )

    revision: str = Field(
        None,
        description="Source control revision identifier for the packaged software.",
    )

    vendor: str = Field(
        None, description="Name of the distributing entity, organization or individual."
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

    title: str = Field(None, description="Human-readable title of the image (string)")

    description: str = Field(
        None,
        description="Human-readable description of the software packaged in the image (string)",
    )

    base_digest: SHA1Str = Field(
        None,
        description="Digest of the image this image is based on (string)",
    )

    class Config:
        alias_generator = lambda field_name: field_name.replace("_", ".")
        allow_population_by_field_name = True
        extra = Extra.forbid

    @classmethod
    def from_labels_annotations(
        cls, labels: Dict[str, str]
    ) -> "OciImageSpecAnnotations":
        data = from_labels(labels, prefix_key=OCI_LABEL_PREFIX, trim_key_head=False)
        return cls.parse_obj(data)

    def to_labels_annotations(self) -> Dict[str, str]:
        labels = to_labels(
            self.dict(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OCI_LABEL_PREFIX,
        )
        return labels


class LabelSchemaAnnotations(BaseModel):
    """
    NOTE:  DEPRECATED IN FAVOUR OF OCI IMAGE SPEC
    """

    schema_version: VersionStr = Field("1.0.0", alias="schema-version")

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

    def to_oci_data(self) -> Dict[str, Any]:
        """Collects data that be converted to OCI labels.

        WARNING: label-schema has be deprecated in favor of OCI image specs
        """
        convertable_data = self.dict(
            include=set(_TO_OCI.keys()), exclude_unset=True, exclude_none=True
        )
        assert set(convertable_data.keys()).issubset(  # nosec
            set(self.__fields__.keys())
        )  # nosec

        oci_data = {_TO_OCI[key]: value for key, value in convertable_data.items()}
        return oci_data
