import urllib.parse
from typing import Annotated, Generic, TypeVar

import packaging.version
from models_library.utils.change_case import camel_to_snake
from models_library.utils.common_validators import trim_string_before
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

from .._utils_pydantic import UriSchema
from ..basic_types import VersionStr


class ApiServerOutputSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=camel_to_snake,
        populate_by_name=True,
        extra="ignore",  # Used to prune extra fields from internal data
        frozen=False,
    )


class ApiServerInputSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=camel_to_snake,
        populate_by_name=True,
        extra="ignore",  # Used to prune extra fields from internal data
        frozen=True,
    )


class BaseService(BaseModel):
    id: Annotated[
        str,
        Field(description="Resource identifier"),
    ]
    version: Annotated[
        VersionStr,
        Field(description="Semantic version number of the resource"),
    ]
    title: Annotated[
        str,
        trim_string_before(max_length=100),
        StringConstraints(max_length=100),
        Field(description="Human readable name"),
    ]
    description: Annotated[
        str | None,
        StringConstraints(
            # NOTE: Place `StringConstraints` before `trim_string_before` for valid OpenAPI schema due to a Pydantic limitation.
            # SEE `test_trim_string_before_with_string_constraints`
            max_length=1000
        ),
        trim_string_before(max_length=1000),
        Field(default=None, description="Description of the resource"),
    ]

    url: Annotated[
        HttpUrl | None,
        UriSchema(),
        Field(description="Link to get this resource"),
    ]

    @property
    def pep404_version(self) -> packaging.version.Version:
        """Rich version type that can be used e.g. to compare"""
        return packaging.version.parse(self.version)

    @property
    def url_friendly_id(self) -> str:
        """Use to pass id as parameter in URLs"""
        return urllib.parse.quote_plus(self.id)

    @property
    def resource_name(self) -> str:
        """Relative resource name"""
        return self.compose_resource_name(self.id, self.version)

    @property
    def name(self) -> str:
        """API standards notation (see api_resources.py)"""
        return self.resource_name

    @classmethod
    def compose_resource_name(cls, key: str, version: str) -> str:
        raise NotImplementedError("Subclasses must implement this method")


DataT = TypeVar("DataT")


class ApiServerEnvelope(BaseModel, Generic[DataT]):
    data: DataT
