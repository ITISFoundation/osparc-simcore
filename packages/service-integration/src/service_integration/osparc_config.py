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
from typing import Any, ClassVar, Literal, NamedTuple

from models_library.callbacks_mapping import CallbacksMapping
from models_library.service_settings_labels import (
    ContainerSpec,
    DynamicSidecarServiceLabels,
    NATRule,
    PathMappingsLabel,
    RestartPolicy,
)
from models_library.services import (
    COMPUTATIONAL_SERVICE_KEY_FORMAT,
    DYNAMIC_SERVICE_KEY_FORMAT,
    BootOptions,
    ServiceDockerData,
    ServiceType,
)
from pydantic import NonNegativeInt, ValidationError
from pydantic.class_validators import root_validator, validator
from pydantic.config import Extra
from pydantic.fields import Field
from pydantic.main import BaseModel

from .compose_spec_model import ComposeSpecification
from .errors import ConfigNotFound
from .labels_annotations import from_labels, to_labels
from .settings import AppSettings
from .yaml_utils import yaml_safe_load

_logger = logging.getLogger(__name__)

CONFIG_FOLDER_NAME = ".osparc"


SERVICE_KEY_FORMATS = {
    ServiceType.COMPUTATIONAL: COMPUTATIONAL_SERVICE_KEY_FORMAT,
    ServiceType.DYNAMIC: DYNAMIC_SERVICE_KEY_FORMAT,
}

# SEE https://docs.docker.com/config/labels-custom-metadata/#label-keys-and-values
#  "Authors of third-party tools should prefix each label key with the reverse DNS notation of a
#   domain they own, such as com.example.some-label ""
# FIXME: review and define a z43-wide inverse DNS e.g. swiss.z43
OSPARC_LABEL_PREFIXES = (
    "io.simcore",
    "simcore.service",
)


## MODELS ---------------------------------------------------------------------------------
#
# Project config -> stored in repo's basedir/.osparc
#


class DockerComposeOverwriteCfg(ComposeSpecification):
    """picks up configurations used to overwrite the docker-compuse output"""

    @classmethod
    def create_default(
        cls, service_name: str | None = None
    ) -> "DockerComposeOverwriteCfg":
        model: "DockerComposeOverwriteCfg" = cls.parse_obj(
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
    def from_yaml(cls, path: Path) -> "DockerComposeOverwriteCfg":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        model: "DockerComposeOverwriteCfg" = cls.parse_obj(data)
        return model


class MetaConfig(ServiceDockerData):
    """Details about general info and I/O configuration of the service

    Necessary for both image- and runtime-spec
    """

    @validator("contact")
    @classmethod
    def check_contact_in_authors(cls, v, values):
        """catalog service relies on contact and author to define access rights"""
        authors_emails = {author.email for author in values["authors"]}
        if v not in authors_emails:
            msg = "Contact {v} must be registered as an author"
            raise ValueError(msg)
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> "MetaConfig":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        model: "MetaConfig" = cls.parse_obj(data)
        return model

    @classmethod
    def from_labels_annotations(cls, labels: dict[str, str]) -> "MetaConfig":
        data = from_labels(
            labels, prefix_key=OSPARC_LABEL_PREFIXES[0], trim_key_head=False
        )
        model: "MetaConfig" = cls.parse_obj(data)
        return model

    def to_labels_annotations(self) -> dict[str, str]:
        return to_labels(
            self.dict(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[0],
            trim_key_head=False,
        )

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
            service_path = service_path.replace("/", ".")

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

    @validator("type_", pre=True)
    @classmethod
    def ensure_backwards_compatible_setting_type(cls, v):
        if v == "resources":
            # renamed in the latest version as
            return "Resources"
        return v

    @validator("value", pre=True)
    @classmethod
    def check_value_against_custom_types(cls, v, values):
        if (type_ := values.get("type_")) and type_ == "ContainerSpec":
            ContainerSpec.parse_obj(v)
        return v


class ValidatingDynamicSidecarServiceLabels(DynamicSidecarServiceLabels):
    class Config:
        extra = Extra.allow
        allow_population_by_field_name = True


def _get_alias_generator(field_name: str) -> str:
    return field_name.replace("_", "-")


class RuntimeConfig(BaseModel):
    """Details about the service runtime

    Necessary for runtime-spec
    """

    compose_spec: ComposeSpecification | None = None
    container_http_entrypoint: str | None = None

    restart_policy: RestartPolicy = RestartPolicy.NO_RESTART

    callbacks_mapping: CallbacksMapping | None = None
    paths_mapping: PathMappingsLabel | None = None
    boot_options: BootOptions = None
    min_visible_inputs: NonNegativeInt | None = None

    containers_allowed_outgoing_permit_list: dict[str, list[NATRule]] | None = None

    containers_allowed_outgoing_internet: set[str] | None = None

    settings: list[SettingsItem] = Field(default_factory=list)

    @root_validator
    @classmethod
    def _callbacks_mapping_cannot_be_none(cls, values):
        if values.get("callbacks_mapping") is None:
            values["callbacks_mapping"] = {}
        return values

    @root_validator(pre=True)
    @classmethod
    def ensure_compatibility(cls, v):
        # NOTE: if changes are applied to `DynamicSidecarServiceLabels`
        # these are also validated when ooil runs.
        try:
            ValidatingDynamicSidecarServiceLabels.parse_obj(v)
        except ValidationError:
            _logger.exception(
                "Could not validate %s via %s",
                DynamicSidecarServiceLabels,
                ValidatingDynamicSidecarServiceLabels,
            )
            raise

        return v

    class Config:
        alias_generator = _get_alias_generator
        allow_population_by_field_name = True
        extra = Extra.forbid

    @classmethod
    def from_yaml(cls, path: Path) -> "RuntimeConfig":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        return cls.parse_obj(data)

    @classmethod
    def from_labels_annotations(cls, labels: dict[str, str]) -> "RuntimeConfig":
        data = from_labels(labels, prefix_key=OSPARC_LABEL_PREFIXES[1])
        return cls.parse_obj(data)

    def to_labels_annotations(self) -> dict[str, str]:
        return to_labels(
            self.dict(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[1],
        )


## FILES -----------------------------------------------------------


class ConfigFileDescriptor(NamedTuple):
    glob_pattern: str
    required: bool = True


class ConfigFilesStructure:
    """
    Defines config file structure and how they
    map to the models
    """

    FILES_GLOBS: ClassVar[dict] = {
        DockerComposeOverwriteCfg.__name__: ConfigFileDescriptor(
            glob_pattern="docker-compose.overwrite.y*ml", required=False
        ),
        MetaConfig.__name__: ConfigFileDescriptor(glob_pattern="metadata.y*ml"),
        RuntimeConfig.__name__: ConfigFileDescriptor(glob_pattern="runtime.y*ml"),
    }

    @staticmethod
    def config_file_path(scope: Literal["user", "project"]) -> Path:
        basedir = Path.cwd()  # assumes project is in CWD
        if scope == "user":
            basedir = Path.home()
        return basedir / ".osparc" / "service-integration.json"

    def search(self, start_dir: Path) -> dict[str, Path]:
        """Tries to match of any of file layouts
        and returns associated config files
        """
        found = {
            configtype: list(start_dir.rglob(pattern))
            for configtype, (pattern, required) in self.FILES_GLOBS.items()
            if required
        }

        if not found:
            raise ConfigNotFound(basedir=start_dir)

        raise NotImplementedError("TODO")

        # TODO:
        # scenarios:
        #   .osparc/meta, [runtime]
        #   .osparc/{service-name}/meta, [runtime]

        # metadata is required, runtime is optional?
