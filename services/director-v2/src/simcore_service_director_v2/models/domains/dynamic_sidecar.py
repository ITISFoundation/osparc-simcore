from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, validator

ComposeSpecModel = Optional[Dict[str, Any]]


class PathsMappingModel(BaseModel):
    inputs_path: str = Field(
        ..., description="path where the service expects all the inputs folder"
    )
    outputs_path: str = Field(
        ..., description="path where the service expects all the outputs folder"
    )
    other_paths: List[str] = Field(
        [],
        description="optional list of path which contents need to be saved and restored",
    )

    @validator("other_paths", always=True)
    @classmethod
    def other_paths_always_a_list(cls, v):
        return [] if v is None else v


class StartServiceSidecarModel(BaseModel):
    user_id: str
    project_id: str
    service_key: str
    service_tag: str
    node_uuid: str

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
            "which will be handeled by the service-sidecar"
        ),
    )
    compose_spec: ComposeSpecModel = Field(
        ...,
        description=(
            "if the user provides a compose_spec, it will be used instead "
            "of compsing one from the service_key and service_tag"
        ),
    )
    target_container: Optional[str] = Field(
        ...,
        description="when the user defines a compose spec, it should pick a container inside the spec to receive traffic on a defined port",
    )

    @validator("target_container")
    @classmethod
    def target_container_must_exist_if_compose_spec_present(
        cls, v, values, **kwargs
    ):  # pylint: disable=unused-argument
        if values.get("compose_spec", None) is not None and v is None:
            raise ValueError(
                "target_container is required when compose_spec is defined. "
                f"The following compose spec was defined: {values['compose_spec']}"
            )
        return v

    @validator("request_scheme")
    @classmethod
    def validate_protocol(cls, v, values, **kwargs):  # pylint: disable=unused-argument
        if v not in {"http", "https"}:
            raise ValueError(
                "target_container is required when compose_spec is defined. "
                f"The following compose spec was defined: {values['compose_spec']}"
            )
        return v


class NodeUUIDModel(BaseModel):
    node_uuid: str