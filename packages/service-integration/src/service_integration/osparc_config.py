""" 'osparc config' is a set of stardard file forms (yaml) that the user fills to describe how his/her service works and
integrates with osparc.

    - config files are stored under '.osparc/' folder in the root repo folder (analogous to other configs like .github, .vscode, etc)
    - configs are parsed and validated into pydantic models
    - models can be serialized/deserialized into label annotations on images. This way, the config is attached to the service
    during it's entire lifetime.
    - config should provide enough information about that context to allow
        - build an image
        - run an container
      on a single command call.
    -
"""

import logging
from pathlib import Path
from typing import Any, Final, Literal

from models_library.basic_types import SHA256Str
from models_library.callbacks_mapping import CallbacksMapping
from models_library.service_settings_labels import (
    ContainerSpec,
    DynamicSidecarServiceLabels,
    PathMappingsLabel,
    RestartPolicy,
)
from models_library.service_settings_nat_rule import NATRule
from models_library.services import BootOptions, ServiceMetaDataPublished, ServiceType
from models_library.services_regex import (
    COMPUTATIONAL_SERVICE_KEY_FORMAT,
    DYNAMIC_SERVICE_KEY_FORMAT,
)
from models_library.services_types import ServiceKey
from models_library.utils.labels_annotations import (
    OSPARC_LABEL_PREFIXES,
    from_labels,
    to_labels,
)
from pydantic import (
    ConfigDict,
    NonNegativeInt,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.fields import Field
from pydantic.main import BaseModel

from .compose_spec_model import ComposeSpecification
from .settings import AppSettings
from .yaml_utils import yaml_safe_load

_logger = logging.getLogger(__name__)

OSPARC_CONFIG_DIRNAME: Final[str] = ".osparc"
OSPARC_CONFIG_COMPOSE_SPEC_NAME: Final[str] = "docker-compose.overwrite.yml"
OSPARC_CONFIG_METADATA_NAME: Final[str] = "metadata.yml"
OSPARC_CONFIG_RUNTIME_NAME: Final[str] = "runtime.yml"


SERVICE_KEY_FORMATS = {
    ServiceType.COMPUTATIONAL: COMPUTATIONAL_SERVICE_KEY_FORMAT,
    ServiceType.DYNAMIC: DYNAMIC_SERVICE_KEY_FORMAT,
}


class DockerComposeOverwriteConfig(ComposeSpecification):
    """Content of docker-compose.overwrite.yml configuration file"""

    @classmethod
    def create_default(
        cls, service_name: str | None = None
    ) -> "DockerComposeOverwriteConfig":
        model: "DockerComposeOverwriteConfig" = cls.model_validate(
            {
                "services": {
                    service_name: {
                        "build": {
                            "dockerfile": "Dockerfile",
                        }
                    }
                }
            }
        )
        return model

    @classmethod
    def from_yaml(cls, path: Path) -> "DockerComposeOverwriteConfig":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        model: "DockerComposeOverwriteConfig" = cls.model_validate(data)
        return model


class MetadataConfig(ServiceMetaDataPublished):
    """Content of metadata.yml configuration file

    Details about general info and I/O configuration of the service
    Necessary for both image- and runtime-spec
    """

    image_digest: SHA256Str | None = Field(
        None,
        description="this is NOT a label, therefore it is EXCLUDED to export",
        exclude=True,
    )

    @field_validator("contact")
    @classmethod
    def _check_contact_in_authors(cls, v, info: ValidationInfo):
        """catalog service relies on contact and author to define access rights"""
        authors_emails = {author.email for author in info.data["authors"]}
        if v not in authors_emails:
            msg = "Contact {v} must be registered as an author"
            raise ValueError(msg)
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> "MetadataConfig":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        model: "MetadataConfig" = cls.model_validate(data)
        return model

    @classmethod
    def from_labels_annotations(cls, labels: dict[str, str]) -> "MetadataConfig":
        data = from_labels(
            labels, prefix_key=OSPARC_LABEL_PREFIXES[0], trim_key_head=False
        )
        model: "MetadataConfig" = cls.model_validate(data)
        return model

    def to_labels_annotations(self) -> dict[str, str]:
        labels: dict[str, str] = to_labels(
            self.model_dump(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[0],
            trim_key_head=False,
        )
        return labels

    def service_name(self) -> str:
        """name used as key in the compose-spec services map"""
        assert isinstance(self.key, str)  # nosec
        return self.key.split("/")[-1].replace(" ", "")

    def image_name(self, settings: AppSettings, registry="local") -> str:
        registry_prefix = f"{settings.REGISTRY_NAME}/" if settings.REGISTRY_NAME else ""
        service_path = self.key
        if registry in "dockerhub":
            # dockerhub allows only one-level names -> dot it
            # TODO: check thisname is compatible with REGEX
            service_path = ServiceKey(service_path.replace("/", "."))

        service_version = self.version
        return f"{registry_prefix}{service_path}:{service_version}"


class SettingsItem(BaseModel):
    # NOTE: this maps to SimcoreServiceSettingLabelEntry
    # It is not reused until agreed how to refactor
    # Instead there is a test that keeps them in sync

    name: str = Field(..., description="The name of the service setting")
    type_: Literal[
        "string",
        "int",
        "integer",
        "number",
        "object",
        "ContainerSpec",
        "Resources",
    ] = Field(
        ...,
        description="The type of the service setting (follows Docker REST API naming scheme)",
        alias="type",
    )
    value: Any = Field(
        ...,
        description="The value of the service setting (shall follow Docker REST API scheme for services",
    )

    @field_validator("type_", mode="before")
    @classmethod
    def ensure_backwards_compatible_setting_type(cls, v):
        if v == "resources":
            # renamed in the latest version as
            return "Resources"
        return v

    @field_validator("value", mode="before")
    @classmethod
    def check_value_against_custom_types(cls, v, info: ValidationInfo):
        if (type_ := info.data.get("type_")) and type_ == "ContainerSpec":
            ContainerSpec.model_validate(v)
        return v


class ValidatingDynamicSidecarServiceLabels(DynamicSidecarServiceLabels):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


def _underscore_as_minus(field_name: str) -> str:
    return field_name.replace("_", "-")


class RuntimeConfig(BaseModel):
    """Details about the service runtime

    Necessary for runtime-spec
    """

    compose_spec: ComposeSpecification | None = None
    container_http_entrypoint: str | None = None

    restart_policy: RestartPolicy = RestartPolicy.NO_RESTART

    callbacks_mapping: CallbacksMapping | None = Field(default_factory=dict)
    paths_mapping: PathMappingsLabel | None = None

    user_preferences_path: Path | None = None
    boot_options: BootOptions | None = None
    min_visible_inputs: NonNegativeInt | None = None

    containers_allowed_outgoing_permit_list: dict[str, list[NATRule]] | None = None

    containers_allowed_outgoing_internet: set[str] | None = None

    settings: list[SettingsItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def ensure_compatibility(cls, v):
        # NOTE: if changes are applied to `DynamicSidecarServiceLabels`
        # these are also validated when ooil runs.
        try:
            ValidatingDynamicSidecarServiceLabels.model_validate(v)
        except ValidationError:
            _logger.exception(
                "Could not validate %s via %s",
                DynamicSidecarServiceLabels,
                ValidatingDynamicSidecarServiceLabels,
            )
            raise

        return v

    model_config = ConfigDict(
        alias_generator=_underscore_as_minus,
        populate_by_name=True,
        extra="forbid",
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "RuntimeConfig":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        return cls.model_validate(data)

    @classmethod
    def from_labels_annotations(cls, labels: dict[str, str]) -> "RuntimeConfig":
        data = from_labels(labels, prefix_key=OSPARC_LABEL_PREFIXES[1])
        return cls.model_validate(data)

    def to_labels_annotations(self) -> dict[str, str]:
        labels: dict[str, str] = to_labels(
            self.model_dump(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[1],
        )
        return labels
