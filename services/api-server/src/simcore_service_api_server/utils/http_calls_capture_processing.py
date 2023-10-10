from pathlib import Path
from typing import Any, Literal, get_args
from urllib.parse import unquote

import httpx
import jsonref
from pydantic import BaseModel, Field, parse_obj_as, root_validator, validator
from simcore_service_api_server.core.settings import (
    CatalogSettings,
    StorageSettings,
    WebServerSettings,
)

service_hosts = Literal["storage", "catalog", "webserver"]


class CapturedParameterSchema(BaseModel):
    title: str | None
    type_: Literal["str", "int", "float", "bool"] | None = Field(
        None, alias="type", optional=True
    )
    pattern: str | None
    format_: Literal["uuid"] | None = Field(None, alias="format", optional=True)
    exclusiveMinimum: bool | None
    minimum: int | None
    anyOf: list["CapturedParameterSchema"] | None
    allOf: list["CapturedParameterSchema"] | None
    oneOf: list["CapturedParameterSchema"] | None

    class Config:
        validate_always = True
        allow_population_by_field_name = True

    @validator("type_", pre=True)
    @classmethod
    def preprocess_type_(cls, val):
        if val == "string":
            val = "str"
        if val == "integer":
            val = "int"
        if val == "boolean":
            val = "bool"
        return val

    @root_validator(pre=False)
    @classmethod
    def check_compatibility(cls, values):
        type_ = values.get("type_")
        pattern = values.get("pattern")
        format_ = values.get("format_")
        anyOf = values.get("anyOf")
        allOf = values.get("allOf")
        oneOf = values.get("oneOf")
        if type_ != "str":
            if pattern is not None or format_ is not None:
                raise ValueError(
                    f"For {type_=} both {pattern=} and {format_=} must be None"
                )
        if type_ is None and oneOf is None and anyOf is None and allOf is None:
            raise ValueError("all of 'type_', 'oneOf', 'anyOf' and 'allOf' were None")

        def _check_no_recursion(v: list["CapturedParameterSchema"]):
            if v is not None and not all(
                elm.anyOf is None and elm.oneOf is None and elm.allOf is None
                for elm in v
            ):
                raise ValueError(
                    "For simplicity we only allow top level schema have oneOf, anyOf or allOf"
                )

        _check_no_recursion(anyOf)
        _check_no_recursion(allOf)
        _check_no_recursion(oneOf)
        return values  # this validator ONLY validates - no modification

    @property
    def regex_pattern(self) -> str:
        # first deal with recursive types:
        if self.oneOf:
            raise NotImplementedError(
                "Current version cannot compute regex patterns in case of oneOf. Please go ahead and implement it yourself."
            )
        if self.anyOf:
            return "|".join([elm.regex_pattern for elm in self.anyOf])
        if self.allOf:
            return "&".join([elm.regex_pattern for elm in self.allOf])

        # now deal with non-recursive cases
        pattern: str | None = None
        if self.pattern is not None:
            pattern = str(self.pattern).removeprefix("^").removesuffix("$")
        else:
            if self.type_ == "int":
                pattern = r"[-+]?\d+"
            elif self.type_ == "float":
                pattern = r"[+-]?\d+(?:\.\d+)?"
            elif self.type_ == "str":
                if self.format_ == "uuid":
                    pattern = r"[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}"
                else:
                    pattern = r".*"  # should match any string
        if pattern is None:
            raise OpenApiSpecIssue(
                f"Encountered invalid {self.type_=} and {self.format_=} combination"
            )
        return pattern


class CapturedParameter(BaseModel):
    in_: Literal["path", "header", "query"] = Field(..., alias="in")
    name: str
    required: bool
    schema_: CapturedParameterSchema = Field(..., alias="schema")
    response_value: str | None = (
        None  # attribute for storing the params value in a concrete response
    )

    class Config:
        validate_always = True
        allow_population_by_field_name = True

    def __hash__(self):
        return hash(
            self.name + self.in_
        )  # it is assumed name is unique within a given path

    def __eq__(self, other):
        return self.name == other.name and self.in_ == other.in_

    @property
    def is_path(self) -> bool:
        return self.in_ == "path"

    @property
    def is_header(self) -> bool:
        return self.in_ == "header"

    @property
    def is_query(self) -> bool:
        return self.in_ == "query"

    @property
    def respx_lookup(self) -> str:
        return rf"(?P<{self.name}>{self.schema_.regex_pattern})"


class PathDescription(BaseModel):
    path: str
    path_parameters: list[CapturedParameter]


def enhance_from_openapi_spec(response: httpx.Response) -> PathDescription:
    assert response.url.host in get_args(
        service_hosts
    ), f"{response.url.host} is not in {service_hosts} - please add it yourself"
    openapi_spec: dict[str, Any] = _get_openapi_specs(response.url.host)
    return _determine_path(
        openapi_spec, Path(response.request.url.raw_path.decode("utf8").split("?")[0])
    )


def _get_openapi_specs(host: service_hosts) -> dict[str, Any]:
    url: str
    if host == "storage":
        settings = StorageSettings()
        url = settings.base_url + "/dev/doc/swagger.json"
    elif host == "catalog":
        settings = CatalogSettings()
        url = settings.base_url + "/api/v0/openapi.json"
    elif host == "webserver":
        settings = WebServerSettings()
        url = settings.base_url + "/dev/doc/swagger.json"
    else:
        raise OpenApiSpecIssue(
            f"{host=} has not been added yet to the testing system. Please do so yourself"
        )
    with httpx.Client() as session:
        # http://127.0.0.1:30010/dev/doc/swagger.json
        # http://127.0.0.1:8006/api/v0/openapi.json
        response = session.get(url)
        response.raise_for_status()
        openapi_spec = jsonref.loads(response.read().decode("utf8"))
        assert isinstance(openapi_spec, dict)
        return openapi_spec


def _determine_path(
    openapi_spec: dict[str, Any], response_path: Path
) -> PathDescription:

    for p in openapi_spec["paths"]:
        openapi_path = Path(p)
        if len(openapi_path.parts) != len(response_path.parts):
            continue
        path_params = {
            param.name: param for param in _get_params(openapi_spec, p) if param.is_path
        }
        if (len(path_params) == 0) and (openapi_path.parts == response_path.parts):
            return PathDescription(
                path=str(response_path), path_parameters=list(path_params.values())
            )
        path_param_indices: tuple[int, ...] = tuple(
            openapi_path.parts.index("{" + name + "}") for name in path_params
        )
        if tuple(
            elm
            for ii, elm in enumerate(openapi_path.parts)
            if ii not in path_param_indices
        ) != tuple(
            elm
            for ii, elm in enumerate(response_path.parts)
            if ii not in path_param_indices
        ):
            continue
        path_param_indices_iter = iter(path_param_indices)
        for key in path_params:
            ii = next(path_param_indices_iter)
            path_params[key].response_value = unquote(response_path.parts[ii])
        return PathDescription(
            path=str(openapi_path),
            path_parameters=list(path_params.values()),
        )
    raise PathNotInOpenApiSpecification(
        f"Could not find a path matching {response_path} in "
    )


def _get_params(
    openapi_spec: dict[str, Any], path: str, method: str | None = None
) -> set[CapturedParameter]:
    """Returns all parameters for the method associated with a given resource (and optionally also a given method)"""
    endpoints: dict[str, Any] | None
    if (endpoints := openapi_spec["paths"].get(path)) is None:
        raise PathNotInOpenApiSpecification(
            f"{path} was not in the openapi specification"
        )
    all_params: list[CapturedParameter] = []
    for verb in [method] if method is not None else list(endpoints):
        if (verb_spec := endpoints.get(verb)) is None:
            raise VerbNotInPath(
                f"the verb '{verb}' was not available in '{path}' in {openapi_spec}"
            )
        if (params := verb_spec.get("parameters")) is None:
            continue
        all_params += parse_obj_as(list[CapturedParameter], params)
    return set(all_params)


class CaptureProcessingException(Exception):
    # base for all the exceptions in this submodule
    pass


class VerbNotInPath(CaptureProcessingException):
    pass


class PathNotInOpenApiSpecification(CaptureProcessingException):
    pass


class OpenApiSpecIssue(CaptureProcessingException):
    pass
