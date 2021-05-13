from pathlib import Path
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, validator

from ..schemas.constants import UserID
from models_library.projects import ProjectID
from models_library.services import SERVICE_KEY_RE
from models_library.basic_regex import VERSION_RE


ComposeSpecModel = Optional[Dict[str, Any]]


class PathsMappingModel(BaseModel):
    inputs_path: Path = Field(
        ..., description="path where the service expects all the inputs folder"
    )
    outputs_path: Path = Field(
        ..., description="path where the service expects all the outputs folder"
    )
    other_paths: List[Path] = Field(
        [],
        description="optional list of path which contents need to be saved and restored",
    )

    @validator("other_paths", always=True)
    @classmethod
    def convert_none_to_empty_list(cls, v):
        return [] if v is None else v


class StartDynamicSidecarModel(BaseModel):
    user_id: UserID
    project_id: ProjectID
    service_key: str = Field(
        ..., description="name of the service", regex=SERVICE_KEY_RE
    )
    service_tag: str = Field(
        ..., description="tag usually also known as version", regex=VERSION_RE
    )

    # these come from the webserver via the director
    request_scheme: str = Field(
        ..., description="Used for the proxy configuration either http or https"
    )
    request_dns: str = Field(..., description="Used for the proxy configuration")

    settings: List[Dict[str, Any]] = Field(
        ...,
        description="settings for the services define by the service maintainer in the labels",
    )
    paths_mapping: PathsMappingModel = Field(
        ...,
        description=(
            "the service explicitly requests where to mount all paths "
            "which will be handeled by the dynamic-sidecar"
        ),
    )
    compose_spec: Optional[ComposeSpecModel] = Field(
        None,
        description=(
            "if the user provides a compose_spec, it will be used instead "
            "of compsing one from the service_key and service_tag"
        ),
    )
    target_container: Optional[str] = Field(
        None,
        description="when the user defines a compose spec, it should pick a container inside the spec to receive traffic on a defined port",
    )

    @validator("target_container")
    @classmethod
    def target_container_must_exist_if_compose_spec_present(cls, v, values):
        if values.get("compose_spec", None) is not None and v is None:
            raise ValueError(
                "simcore.service.target_container is required when compose_spec is defined. "
                f"The following compose spec was defined: {values['compose_spec']}"
            )
        return v

    @validator("request_scheme")
    @classmethod
    def validate_protocol(cls, v):
        if v not in {"http", "https"}:
            raise ValueError(f"provided request_scheme={v} must be 'http' or 'https'")
        return v

    class Config:
        schema_extra = {
            "example": {
                "user_id": 10,
                "project_id": "eb2ba037-4fb6-45da-80c8-00809399f24a",
                "service_key": "simcore/services/dynamic/httpbin-dynamic-sidecar-compose",
                "service_tag": "1.0.1",
                "request_scheme": "http",
                "request_dns": "localhost",
                "settings": [
                    {
                        "name": "resources",
                        "type": "Resources",
                        "value": {"mem_limit": 17179869184, "cpu_limit": 1000000000},
                    },
                    {"name": "ports", "type": "int", "value": 80},
                    {
                        "name": "constraints",
                        "type": "string",
                        "value": ["node.platform.os == linux"],
                    },
                ],
                "compose_spec": {
                    "version": "2.3",
                    "services": {
                        "httpbin-docker-compose-spec": {
                            "image": "${REGISTRY_URL}/simcore/services/dynamic/httpbin-dynamic-sidecar-compose:${SERVICE_TAG}",
                            "environment": ["MOCK_VALUE=MOCK_VALUE"],
                            "volumes": ["/tmp/nothing:/tmp/nothing"],  # nosec
                        }
                    },
                },
                "target_container": "httpbin-docker-compose-spec",
            }
        }
