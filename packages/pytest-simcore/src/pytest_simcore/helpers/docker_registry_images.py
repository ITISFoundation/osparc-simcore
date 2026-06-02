from typing import Any, Literal, Protocol, TypedDict


class NodeRequirementsDict(TypedDict):
    CPU: float
    RAM: float


class ServiceExtrasDict(TypedDict):
    node_requirements: NodeRequirementsDict
    build_date: str
    vcs_ref: str
    vcs_url: str


class ServiceDescriptionDict(TypedDict):
    key: str
    version: str
    type: Literal["computational", "dynamic"]


class ServiceInRegistryInfoDict(TypedDict):
    service_description: ServiceDescriptionDict
    docker_labels: dict[str, Any]
    image_path: str
    internal_port: int | None
    entry_point: str
    service_extras: ServiceExtrasDict


class PushServicesCallable(Protocol):
    async def __call__(
        self,
        *,
        number_of_computational_services: int,
        number_of_interactive_services: int,
        inter_dependent_services: bool = False,
        bad_json_format: bool = False,
        version="1.0.",
        override_registry_url: str | None = None,
    ) -> list[ServiceInRegistryInfoDict]: ...
