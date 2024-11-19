from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .httpx_calls_capture_errors import OpenApiSpecError


class CapturedParameterSchema(BaseModel):
    title: str | None = None
    type_: Literal["str", "int", "float", "bool"] | None = Field(None, alias="type")
    pattern: str | None = None
    format_: Literal["uuid"] | None = Field(None, alias="format")
    exclusiveMinimum: bool | None = None
    minimum: int | float | None = None
    anyOf: list["CapturedParameterSchema"] | None = None
    allOf: list["CapturedParameterSchema"] | None = None
    oneOf: list["CapturedParameterSchema"] | None = None

    class Config:
        validate_always = True
        allow_population_by_field_name = True

    @field_validator("type_", mode="before")
    @classmethod
    def preprocess_type_(cls, val):
        if val == "string":
            val = "str"
        if val == "integer":
            val = "int"
        if val == "boolean":
            val = "bool"
        return val

    @model_validator(mode="after")
    @classmethod
    def check_compatibility(cls, values):
        type_ = values.type_
        pattern = values.pattern
        format_ = values.format_
        anyOf = values.anyOf
        allOf = values.allOf
        oneOf = values.oneOf
        if not any([type_, oneOf, anyOf, allOf]):
            type_ = "str"  # this default is introduced because we have started using json query params in the webserver
            values.type_ = type_
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
        if self.anyOf is not None:
            return "|".join(
                [
                    elm.regex_pattern
                    for elm in self.anyOf  # pylint:disable=not-an-iterable
                ]
            )
        if self.allOf is not None:
            return "&".join(
                [
                    elm.regex_pattern
                    for elm in self.allOf  # pylint:disable=not-an-iterable
                ]
            )

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
    schema_: Annotated[CapturedParameterSchema, Field(..., alias="schema")]
    response_value: str | None = (
        None  # attribute for storing the params value in a concrete response
    )
    model_config = ConfigDict(validate_default=True, populate_by_name=True)

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

    def to_path_regex(self) -> str:
        path_regex: str = f"{self.path}"
        for param in self.path_parameters:
            path_regex = path_regex.replace("{" + param.name + "}", param.respx_lookup)
        return path_regex
