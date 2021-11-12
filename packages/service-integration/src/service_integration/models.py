from typing import Dict, TypedDict

ServiceName = str


# https://github.com/compose-spec/compose-spec/blob/master/spec.md


class BuildSpecDict(TypedDict):
    labels: Dict[str, str]


class ServiceSpecDict(TypedDict):
    image: str
    build: BuildSpecDict
    port: int


class ComposeSpecDict(TypedDict):
    services: Dict[ServiceName, ServiceSpecDict]
