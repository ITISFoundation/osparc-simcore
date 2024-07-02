from typing import Any, Literal, TypeAlias, TypedDict

ServiceNameStr: TypeAlias = str


class ComposeSpecDict(TypedDict):
    version: str
    services: dict[str, Any]


class StackDict(TypedDict):
    name: str
    compose: ComposeSpecDict


class StacksDeployedDict(TypedDict):
    stacks: dict[Literal["core", "ops"], StackDict]
    services: list[ServiceNameStr]


class RegisteredUserDict(TypedDict):
    first_name: str
    last_name: str
    email: str
    password: str
    api_key: str
    api_secret: str


class ServiceInfoDict(TypedDict):
    name: str
    version: str
    schema: dict[str, Any]
