import json
from http import HTTPStatus
from typing import Any, Literal

import httpx
from fastapi import status
from pydantic import BaseModel, Field, root_validator, validator


class CaptureProcessingError(Exception):
    # base for all the exceptions in this submodule
    pass


class VerbNotInPathError(CaptureProcessingError):
    pass


class PathNotInOpenApiSpecError(CaptureProcessingError):
    pass


class OpenApiSpecError(CaptureProcessingError):
    pass


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
        if not any([type_, oneOf, anyOf, allOf]):
            type_ = "str"  # this default is introduced because we have started using json query params in the webserver
            values["type_"] = type_
        if type_ != "str" and any([pattern, format_]):
            msg = f"For {type_=} both {pattern=} and {format_=} must be None"
            raise ValueError(msg)

        def _check_no_recursion(v: list["CapturedParameterSchema"]):
            if v is not None and not all(
                elm.anyOf is None and elm.oneOf is None and elm.allOf is None
                for elm in v
            ):
                msg = "For simplicity we only allow top level schema have oneOf, anyOf or allOf"
                raise ValueError(msg)

        _check_no_recursion(anyOf)
        _check_no_recursion(allOf)
        _check_no_recursion(oneOf)
        return values

    @property
    def regex_pattern(self) -> str:
        # first deal with recursive types:
        if self.oneOf:
            msg = "Current version cannot compute regex patterns in case of oneOf. Please go ahead and implement it yourself."
            raise NotImplementedError(msg)
        if self.anyOf:
            return "|".join([elm.regex_pattern for elm in self.anyOf])
        if self.allOf:
            return "&".join([elm.regex_pattern for elm in self.allOf])

        # now deal with non-recursive cases
        pattern: str | None = None
        if self.pattern is not None:
            pattern = str(self.pattern).removeprefix("^").removesuffix("$")
        elif self.type_ == "int":
            pattern = r"[-+]?\d+"
        elif self.type_ == "float":
            pattern = r"[+-]?\d+(?:\.\d+)?"
        elif self.type_ == "str":
            if self.format_ == "uuid":
                pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-(1|3|4|5)[0-9a-fA-F]{3}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
            else:
                pattern = r"[^/]*"  # should match any string not containing "/"
        if pattern is None:
            msg = f"Encountered invalid {self.type_=} and {self.format_=} combination"
            raise OpenApiSpecError(msg)
        return pattern


class CapturedParameter(BaseModel):
    in_: Literal["path", "header", "query"] = Field(..., alias="in")
    name: str
    required: bool
    schema_: CapturedParameterSchema = Field(..., alias="schema")
    response_value: str | None = (
        None  # attribute for storing the params value in a concrete response
    )


class PathDescription(BaseModel):
    path: str
    path_parameters: list[CapturedParameter]


class HttpApiCallCaptureModel(BaseModel):
    """
    Captures relevant information of a call to the http api
    """

    name: str
    description: str
    method: Literal["GET", "PUT", "POST", "PATCH", "DELETE"]
    host: str
    path: PathDescription | str
    query: str | None = None
    request_payload: dict[str, Any] | None = None
    response_body: dict[str, Any] | list | None = None
    status_code: HTTPStatus = Field(default=status.HTTP_200_OK)

    @classmethod
    def create_from_response(
        cls,
        response: httpx.Response,
        *,
        name: str,
        description: str = "",
        enhance_from_openapi_specs: bool = True,
    ) -> "HttpApiCallCaptureModel":
        request = response.request

        path: PathDescription | str
        if enhance_from_openapi_specs:
            path = enhance_from_openapi_spec(response)
        else:
            path = response.request.url.path

        return cls(
            name=name,
            description=description or f"{request}",
            method=request.method,
            host=request.url.host,
            path=path,
            query=request.url.query.decode() or None,
            request_payload=json.loads(request.content.decode())
            if request.content
            else None,
            response_body=response.json() if response.content else None,
            status_code=HTTPStatus(response.status_code),
        )

    def __str__(self) -> str:
        return f"{self.description: self.request_desc}"

    @property
    def request_desc(self) -> str:
        return f"{self.method} {self.path}"

    def as_response(self) -> httpx.Response:
        return httpx.Response(status_code=self.status_code, json=self.response_body)


def get_captured(name: str, response: httpx.Response) -> HttpApiCallCaptureModel:
    return HttpApiCallCaptureModel.create_from_response(response, name=name)
