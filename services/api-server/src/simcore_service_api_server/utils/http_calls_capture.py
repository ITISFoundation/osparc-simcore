import json
from http import HTTPStatus
from pathlib import Path
from typing import Any, Iterator, Literal

import httpx
from pydantic import BaseModel, Field, parse_obj_as, root_validator, validator
from simcore_service_api_server.core.settings import StorageSettings


class HttpApiCallCaptureModel(BaseModel):
    """
    Captures relevant information of a call to the http api
    """

    name: str
    description: str
    method: Literal["GET", "PUT", "POST", "PATCH", "DELETE"]
    host: str
    path: str
    query: str | None = None
    request_payload: dict[str, Any] | None = None
    response_body: dict[str, Any] | list | None = None
    status_code: HTTPStatus = Field(default=HTTPStatus.OK)

    @classmethod
    def create_from_response(
        cls, response: httpx.Response, name: str, description: str = ""
    ) -> "HttpApiCallCaptureModel":
        request = response.request

        url_path: UrlPath = preprocess_response(response)

        return cls(
            name=name,
            description=description or f"{request}",
            method=request.method,
            host=url_path.path,
            path=request.url.path,
            query=request.url.query.decode() or None,
            request_payload=json.loads(request.content.decode())
            if request.content
            else None,
            response_body=response.json() if response.content else None,
            status_code=response.status_code,
        )

    def __str__(self) -> str:
        return f"{self.description: self.request_desc}"

    @property
    def request_desc(self) -> str:
        return f"{self.method} {self.path}"


def get_captured_as_json(name: str, response: httpx.Response) -> str:
    capture_json: str = HttpApiCallCaptureModel.create_from_response(
        response, name=name
    ).json(indent=1)
    return f"{capture_json}"


# tooling for processing response


class ParamSchema(BaseModel):
    title: str | None
    param_type: Literal[
        "str", "string", "int", "integer", "float", "bool", "boolean"
    ] | None = Field(..., alias="type", optional=True)
    pattern: str | None
    format: Literal["uuid"] | None
    exclusiveMinimum: bool | None
    minimum: int | None
    anyOf: list["ParamSchema"] | None

    @validator("param_type")
    def validate_param_type(cls, val):
        if val == "string":
            val = "str"
        if val == "integer":
            val = "int"
        if val == "boolean":
            val = "bool"
        return val

    @root_validator(pre=False)
    def check_compatibility(cls, values):
        param_type = values.get("param_type")
        pattern = values.get("pattern")
        format = values.get("format")
        anyOf = values.get("anyOf")
        if param_type != "str":
            if pattern is not None or format is not None:
                raise ValueError(
                    f"For {param_type=} both {pattern=} and {format=} must be None"
                )
        if anyOf is None and param_type is None:
            raise ValueError(f"anyOf and type cannot both be None")
        return {
            "title": values.get("title"),
            "param_type": param_type,
            "pattern": pattern,
            "format": format,
            "exclusiveMinimum": values.get("exclusiveMinimum"),
            "minimum": values.get("minimum"),
        }

    @property
    def regex_pattern(self) -> str:
        if (pattern := self.pattern) is not None:
            return pattern
        else:
            if self.param_type == "int":
                return r"^[+-]?[1-9][0-9]*|0$"
            elif self.param_type == "float":
                return r"^[+-]?\d+(?:\.\d+)?$"
            elif self.param_type == "str":
                if self.format == "uuid":
                    return r"^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}$"
        raise OpenApiSpecIssue(
            f"Encountered invalid {self.param_type=} and {self.format=} combination"
        )


class Param(BaseModel):
    variable_type: Literal["path", "header", "query"] = Field(..., alias="in")
    name: str
    required: bool
    param_schema: ParamSchema = Field(..., alias="schema")

    def __hash__(self):
        return hash(
            self.name + self.variable_type
        )  # it is assumed name is unique within a given path

    def __eq__(self, other):
        return self.name == other.name and self.variable_type == other.variable_type

    @property
    def is_path(self) -> bool:
        return self.variable_type == "path"

    @property
    def is_header(self) -> bool:
        return self.variable_type == "header"

    @property
    def is_query(self) -> bool:
        return self.variable_type == "query"


class UrlPath(BaseModel):
    path: str
    path_parameters: set[Param]


def preprocess_response(response: httpx.Response) -> UrlPath:
    openapi_spec: dict[str, Any] = get_openapi_specs(response.url.host)
    return _determine_path(openapi_spec, response)


def get_openapi_specs(host: str) -> dict[str, Any]:
    url: str
    if host == "storage":
        settings = StorageSettings()
        url = settings.base_url + "/dev/doc/swagger.json"
    else:
        raise OpenApiSpecIssue(
            f"{host} has not been added yet to the testing system. Please do so yourself"
        )
    with httpx.Client() as session:
        # http://127.0.0.1:30010/dev/doc/swagger.json
        # http://127.0.0.1:8006/api/v0/openapi.json
        response = session.get(url)
        response.raise_for_status()
        return response.json()


def _determine_path(openapi_spec: dict[str, Any], response: httpx.Response) -> UrlPath:

    response_path = Path(response.request.url.raw_path.decode("utf8").split("?")[0])
    for p in openapi_spec["paths"]:
        openapi_path = Path(p)
        if len(openapi_path.parts) != len(response_path.parts):
            continue
        path_params = {
            param.name: param for param in _get_params(openapi_spec, p) if param.is_path
        }
        if (len(path_params) == 0) and (openapi_path.parts == response_path.parts):
            return UrlPath(
                path=str(response_path), path_parameters=set(path_params.values())
            )
        else:
            path_param_indices: tuple[int] = tuple(
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
            mock_path_parts: list[str] = list(openapi_path.parts)
            path_params_iter: Iterator[tuple[str, Any]] = iter(path_params.items())
            for ii in path_param_indices:
                _, param = next(path_params_iter)
                mock_path_parts[ii] = param.schema.regex_pattern
            return UrlPath(
                path=r"/".join(mock_path_parts),
                path_parameters=set(path_params.values()),
            )
    raise PathNotInOpenApiSpecification(
        f"Could not find a path matching {response_path} in "
    )


def _get_params(
    openapi_spec: dict[str, Any], path: str, verb: str | None = None
) -> set[Param]:
    """Returns all parameters for the verbs associated with a given resource (and optionally also a given verb)"""
    endpoints: dict[str, Any] | None
    if (endpoints := openapi_spec["paths"].get(path)) is None:
        raise PathNotInOpenApiSpecification(
            f"{path} was not in the openapi specification"
        )
    all_params: list[Param] = []
    for verb in [verb] if verb is not None else list(endpoints):
        if (verb_spec := endpoints.get(verb)) is None:
            raise VerbNotInPath(
                f"the verb '{verb}' was not available in '{path}' in {openapi_spec}"
            )
        if (params := verb_spec["parameters"]) is None:
            continue
        all_params += parse_obj_as(list[Param], params)
    return set(all_params)


class VerbNotInPath(Exception):
    pass


class PathNotInOpenApiSpecification(Exception):
    pass


class OpenApiSpecIssue(Exception):
    pass
