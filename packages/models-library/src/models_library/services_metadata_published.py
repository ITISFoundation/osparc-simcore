from datetime import datetime
from typing import Any, ClassVar, Final, TypeAlias

from pydantic import Extra, Field, NonNegativeInt

from .basic_regex import SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS
from .boot_options import BootOption, BootOptions
from .emails import LowerCaseEmailStr
from .services_authoring import Author, Badge
from .services_base import ServiceBase, ServiceKeyVersion
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
        "example_service_defined_boot_mode": BootOption.Config.schema_extra["examples"][
            0
        ],
        "example_service_defined_theme_selection": BootOption.Config.schema_extra[
            "examples"
        ][1],
    },
    "min-visible-inputs": 2,
}


class ServiceMetaDataPublished(ServiceKeyVersion, ServiceBase):
    """
    Service metadata at publication time

    - read-only (can only be changed overwriting the image labels in the registry)
    - base metaddata
    - injected in the image labels

    NOTE: This model is serialized in .osparc/metadata.yml and in the labels of the docker image
    """

    version_display: str | None = Field(
        None,
        description="A user-friendly or marketing name for the release."
        " This can be used to reference the release in a more readable and recognizable format, such as 'Matterhorn Release,' 'Spring Update,' or 'Holiday Edition.'"
        " This name is not used for version comparison but is useful for communication and documentation purposes.",
    )

    release_date: datetime | None = Field(
        None,
        description="A timestamp when the specific version of the service was released."
        " This field helps in tracking the timeline of releases and understanding the sequence of updates."
        " A timestamp string should be formatted as YYYY-MM-DD[T]HH:MM[:SS[.ffffff]][Z or [±]HH[:]MM]",
    )

    integration_version: str | None = Field(
        None,
        alias="integration-version",
        description="This version is used to maintain backward compatibility when there are changes in the way a service is integrated into the framework",
        regex=SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS,
    )

    service_type: ServiceType = Field(
        ...,
        alias="type",
        description="service type",
        examples=["computational"],
    )

    badges: list[Badge] | None = Field(None)

    authors: list[Author] = Field(..., min_items=1)
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

    class Config:
        description = "Description of a simcore node 'class' with input and output"
        extra = Extra.forbid
        frozen = False  # overrides config from ServiceKeyVersion.
        allow_population_by_field_name = True

        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                _EXAMPLE,
                _EXAMPLE_W_BOOT_OPTIONS_AND_NO_DISPLAY_ORDER,
                # latest
                {
                    **_EXAMPLE_W_BOOT_OPTIONS_AND_NO_DISPLAY_ORDER,
                    "version_display": "Matterhorn Release",
                    "release_date": "2024-05-31T13:45:30",
                },
            ]
        }
