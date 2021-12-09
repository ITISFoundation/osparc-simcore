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

import io
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from models_library.services import (
    COMPUTATIONAL_SERVICE_KEY_FORMAT,
    DYNAMIC_SERVICE_KEY_FORMAT,
    ServiceDockerData,
    ServiceType,
)
from pydantic.class_validators import validator
from pydantic.fields import Field
from pydantic.main import BaseModel, Extra

from .compose_spec_model import ComposeSpecification
from .context import IntegrationContext
from .errors import ConfigNotFound
from .labels_annotations import from_labels, to_labels
from .yaml_utils import yaml_safe_load
from models_library.service_settings_labels import PathMappingsLabel, RestartPolicy
from models_library.services import BootOptions

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

COMPOSE_OVERWRITE_DEFAULTS = """
services:
  {service_name}:
    build:
      dockerfile: Dockerfile
"""


class DockerComposeOverwriteCfg(ComposeSpecification):
    """picks up configurations used to overwrite the docker-compuse output"""

    @classmethod
    def from_yaml(
        cls, path: Optional[Path], service_name: Optional[str] = None
    ) -> "DockerComposeOverwriteCfg":
        """Loads from the file or creates the content of the file if missing"""
        if path is None:
            if service_name is None:
                raise ValueError("Must provide a 'service_name' when path is missing")

            string_io = io.StringIO(
                COMPOSE_OVERWRITE_DEFAULTS.format(service_name=service_name)
            )
            return cls.parse_obj(yaml_safe_load(string_io))
        with path.open() as fh:
            data = yaml_safe_load(fh)
        return cls.parse_obj(data)


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
            raise ValueError("Contact {v} must be registered as an author")
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> "MetaConfig":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        return cls.parse_obj(data)

    @classmethod
    def from_labels_annotations(cls, labels: Dict[str, str]) -> "MetaConfig":
        data = from_labels(
            labels, prefix_key=OSPARC_LABEL_PREFIXES[0], trim_key_head=False
        )
        return cls.parse_obj(data)

    def to_labels_annotations(self) -> Dict[str, str]:
        labels = to_labels(
            self.dict(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[0],
            trim_key_head=False,
        )
        return labels

    def service_name(self) -> str:
        """name used as key in the compose-spec services map"""
        return self.key.split("/")[-1].replace(" ", "")

    def image_name(
        self, integration_context: IntegrationContext, registry="local"
    ) -> str:
        registry_prefix = (
            f"{integration_context.REGISTRY_NAME}/"
            if integration_context.REGISTRY_NAME
            else ""
        )
        service_path = self.key
        if registry in "dockerhub":
            # dockerhub allows only one-level names -> dot it
            # TODO: check thisname is compatible with REGEX
            service_path = service_path.replace("/", ".")

        service_version = self.version
        return f"{registry_prefix}{service_path}:{service_version}"


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


class RuntimeConfig(BaseModel):
    """Details about the service runtime

    Necessary for runtime-spec
    """

    compose_spec: Optional[ComposeSpecification] = None
    container_http_entrypoint: Optional[str] = None

    restart_policy: RestartPolicy = RestartPolicy.NO_RESTART

    paths_mapping: Optional[PathMappingsLabel] = None
    boot_options: BootOptions = None

    settings: List[SettingsItem] = []

    class Config:
        alias_generator = lambda field_name: field_name.replace("_", "-")
        allow_population_by_field_name = True
        extra = Extra.forbid

    @classmethod
    def from_yaml(cls, path: Path) -> "RuntimeConfig":
        with path.open() as fh:
            data = yaml_safe_load(fh)
        return cls.parse_obj(data)

    @classmethod
    def from_labels_annotations(cls, labels: Dict[str, str]) -> "RuntimeConfig":
        data = from_labels(labels, prefix_key=OSPARC_LABEL_PREFIXES[1])
        return cls.parse_obj(data)

    def to_labels_annotations(self) -> Dict[str, str]:
        labels = to_labels(
            self.dict(exclude_unset=True, by_alias=True, exclude_none=True),
            prefix_key=OSPARC_LABEL_PREFIXES[1],
        )
        return labels


## FILES -----------------------------------------------------------
class ConfigFilesStructure:
    """
    Defines config file structure and how they
    map to the models
    """

    FILES_GLOBS = {
        # TODO: below DockerComposeOverwrite might not be required, maybe remove?
        DockerComposeOverwriteCfg.__name__: "docker-compose.overwrite.y*ml",
        MetaConfig.__name__: "metadata.y*ml",
        RuntimeConfig.__name__: "runtime.y*ml",
    }

    @staticmethod
    def config_file_path(scope: Literal["user", "project"]) -> Path:
        basedir = Path.cwd()  # assumes project is in CWD
        if scope == "user":
            basedir = Path.home()
        return basedir / ".osparc" / "service-integration.json"

    def search(self, start_dir: Path) -> Dict[str, Path]:
        """Tries to match of any of file layouts
        and returns associated config files
        """
        found = {
            configtype: list(start_dir.rglob(pattern))
            for configtype, pattern in self.FILES_GLOBS.items()
        }

        if not found:
            raise ConfigNotFound(basedir=start_dir)

        raise NotImplementedError("TODO")

        # TODO:
        # scenarios:
        #   .osparc/meta, [runtime]
        #   .osparc/{service-name}/meta, [runtime]

        # metadata is required, runtime is optional?
