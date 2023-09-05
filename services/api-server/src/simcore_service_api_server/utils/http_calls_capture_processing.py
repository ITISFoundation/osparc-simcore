from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote

import httpx
import jsonref
from pydantic import BaseModel, Field, parse_obj_as, root_validator, validator
from simcore_service_api_server.core.settings import CatalogSettings, StorageSettings


class ParamSchema(BaseModel):
    title: str | None
    param_type: Literal["str", "int", "float", "bool"] | None = Field(
        None, alias="type", optional=True
    )
    pattern: str | None
    param_format: Literal["uuid"] | None = Field(None, alias="format", optional=True)
    exclusiveMinimum: bool | None
    minimum: int | None
    anyOf: list["ParamSchema"] | None
    allOf: list["ParamSchema"] | None
    oneOf: list["ParamSchema"] | None

    class Config:
        validate_always = True
        allow_population_by_field_name = True

    @validator("param_type", pre=True)
    @classmethod
    def preprocess_param_type(cls, val):
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
        param_type = values.get("param_type")
        pattern = values.get("pattern")
        param_format = values.get("param_format")
        anyOf = values.get("anyOf")
        allOf = values.get("allOf")
        oneOf = values.get("oneOf")
        if param_type != "str":
            if pattern is not None or param_format is not None:
                raise ValueError(
                    f"For {param_type=} both {pattern=} and {param_format=} must be None"
                )
        if param_type is None and oneOf is None and anyOf is None and allOf is None:
            raise ValueError(
                "all of 'param_type', 'oneOf', 'anyOf' and 'allOf' were None"
            )

        def check_no_recursion(v: list["ParamSchema"]):
            if v is not None and not all(
                elm.anyOf is None and elm.oneOf is None and elm.allOf is None
                for elm in v
            ):
                raise ValueError(
                    "For simplicity we only allow top level schema have oneOf, anyOf or allOf"
                )

        check_no_recursion(anyOf)
        check_no_recursion(allOf)
        check_no_recursion(oneOf)
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
            pattern = str(self.pattern)
            pattern = pattern.removeprefix("^")
            pattern = pattern.removesuffix("$")
        else:
            if self.param_type == "int":
                pattern = r"[-+]?\d+"
            elif self.param_type == "float":
                pattern = r"[+-]?\d+(?:\.\d+)?"
            elif self.param_type == "str":
                if self.param_format == "uuid":
                    pattern = r"[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}"
                else:
                    pattern = r".*"  # should match any string
        if pattern is None:
            raise OpenApiSpecIssue(
                f"Encountered invalid {self.param_type=} and {self.param_format=} combination"
            )
        return pattern


class Param(BaseModel):
    variable_type: Literal["path", "header", "query"] = Field(..., alias="in")
    name: str
    required: bool
    param_schema: ParamSchema = Field(..., alias="schema")
    response_value: str | None = (
        None  # attribute for storing the params value in a concrete response
    )

    class Config:
        validate_always = True
        allow_population_by_field_name = True

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

    @property
    def regex_lookup(self) -> str:
        return rf"(?P<{self.name}>{self.param_schema.regex_pattern})"


class PathDescription(BaseModel):
    path: str
    path_parameters: list[Param]


def preprocess_response(response: httpx.Response) -> PathDescription:
    openapi_spec: jsonref.JsonRef = get_openapi_specs(response.url.host)
    return _determine_path(
        openapi_spec, Path(response.request.url.raw_path.decode("utf8").split("?")[0])
    )


def get_openapi_specs(host: Literal["storage", "catalog"]) -> jsonref.JsonRef:
    url: str
    if host == "storage":
        settings = StorageSettings()
        url = settings.base_url + "/dev/doc/swagger.json"
    elif host == "catalog":
        settings = CatalogSettings()
        url = settings.base_url + "/api/v0/openapi.json"
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
        assert isinstance(openapi_spec, jsonref.JsonRef)
        return openapi_spec


def _determine_path(
    openapi_spec: jsonref.JsonRef, response_path: Path
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
        if (params := verb_spec.get("parameters")) is None:
            continue
        all_params += parse_obj_as(list[Param], params)
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
