from datetime import datetime
from typing import Final, TypeAlias

from pydantic import ConfigDict, Field, NonNegativeInt

from .basic_types import SemanticVersionStr
from .boot_options import BootOption, BootOptions
from .emails import LowerCaseEmailStr
from .services_authoring import Author, Badge
from .services_base import ServiceBaseDisplay, ServiceKeyVersion
from .services_constants import ANY_FILETYPE
from .services_enums import ServiceType
from .services_io import ServiceInput, ServiceOutput
from .services_types import ServicePortKey

ServiceInputsDict: TypeAlias = dict[ServicePortKey, ServiceInput]
ServiceOutputsDict: TypeAlias = dict[ServicePortKey, ServiceOutput]


_EXAMPLE: Final = {
    "name": "oSparc Python Runner",
    "key": "simcore/services/comp/osparc-python-runner",
    "type": "computational",
    "integration-version": "1.0.0",
    "progress_regexp": "^(?:\\[?PROGRESS\\]?:?)?\\s*(?P<value>[0-1]?\\.\\d+|\\d+\\s*(?P<percent_sign>%))",
    "version": "1.7.0",
    "description": "oSparc Python Runner",
    "contact": "smith@company.com",
    "authors": [
        {
            "name": "John Smith",
            "email": "smith@company.com",
            "affiliation": "Company",
        },
        {
            "name": "Richard Brown",
            "email": "brown@uni.edu",
            "affiliation": "University",
        },
    ],
    "inputs": {
        "input_1": {
            "displayOrder": 1,
            "label": "Input data",
            "description": "Any code, requirements or data file",
            "type": ANY_FILETYPE,
        }
    },
    "outputs": {
        "output_1": {
            "displayOrder": 1,
            "label": "Output data",
            "description": "All data produced by the script is zipped as output_data.zip",
            "type": ANY_FILETYPE,
            "fileToKeyMap": {"output_data.zip": "output_1"},
        }
    },
}

_EXAMPLE_W_BOOT_OPTIONS_AND_NO_DISPLAY_ORDER = {
    **_EXAMPLE,
    "description": "oSparc Python Runner with boot options",
    "inputs": {
        "input_1": {
            "label": "Input data",
            "description": "Any code, requirements or data file",
            "type": ANY_FILETYPE,
        }
    },
    "outputs": {
        "output_1": {
            "label": "Output data",
            "description": "All data produced by the script is zipped as output_data.zip",
            "type": ANY_FILETYPE,
            "fileToKeyMap": {"output_data.zip": "output_1"},
        }
    },
    "boot-options": {
        "example_service_defined_boot_mode": BootOption.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
        "example_service_defined_theme_selection": BootOption.model_config["json_schema_extra"]["examples"][1],  # type: ignore [index]
    },
    "min-visible-inputs": 2,
}


class ServiceMetaDataPublished(ServiceKeyVersion, ServiceBaseDisplay):
    """
    Service metadata at publication time

    - read-only (can only be changed overwriting the image labels in the registry)
    - base metaddata
    - injected in the image labels

    NOTE: This model is serialized in .osparc/metadata.yml and in the labels of the docker image
    """

    release_date: datetime | None = Field(
        None,
        description="A timestamp when the specific version of the service was released."
        " This field helps in tracking the timeline of releases and understanding the sequence of updates."
        " A timestamp string should be formatted as YYYY-MM-DD[T]HH:MM[:SS[.ffffff]][Z or [±]HH[:]MM]",
    )

    integration_version: SemanticVersionStr | None = Field(
        None,
        alias="integration-version",
        description="This version is used to maintain backward compatibility when there are changes in the way a service is integrated into the framework",
    )

    service_type: ServiceType = Field(
        ...,
        alias="type",
        description="service type",
        examples=["computational"],
    )

    badges: list[Badge] | None = Field(None, deprecated=True)

    authors: list[Author] = Field(..., min_length=1)
    contact: LowerCaseEmailStr = Field(
        ...,
        description="email to correspond to the authors about the node",
        examples=["lab@net.flix"],
    )
    inputs: ServiceInputsDict | None = Field(
        ..., description="definition of the inputs of this node"
    )
    outputs: ServiceOutputsDict | None = Field(
        ..., description="definition of the outputs of this node"
    )

    boot_options: BootOptions | None = Field(
        None,
        alias="boot-options",
        description="Service defined boot options. These get injected in the service as env variables.",
    )

    min_visible_inputs: NonNegativeInt | None = Field(
        None,
        alias="min-visible-inputs",
        description=(
            "The number of 'data type inputs' displayed by default in the UI. "
            "When None all 'data type inputs' are displayed."
        ),
    )

    progress_regexp: str | None = Field(
        None,
        alias="progress_regexp",
        description="regexp pattern for detecting computational service's progress",
    )

    # SEE https://github.com/opencontainers/image-spec/blob/main/annotations.md#pre-defined-annotation-keys
    image_digest: str | None = Field(
        None,
        description="Image manifest digest. Note that this is NOT injected as an image label",
    )

    model_config = ConfigDict(
        extra="forbid",
        frozen=False,
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                _EXAMPLE,  # type: ignore[list-item]
                _EXAMPLE_W_BOOT_OPTIONS_AND_NO_DISPLAY_ORDER,  # type: ignore[list-item]
                # latest
                {
                    **_EXAMPLE_W_BOOT_OPTIONS_AND_NO_DISPLAY_ORDER,  # type: ignore[dict-item]
                    "version_display": "Matterhorn Release",
                    "description_ui": True,
                    "release_date": "2024-05-31T13:45:30",
                },
            ]
        },
    )
