# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Annotated, Any

import fastapi
import pydantic
import pytest
from fastapi import FastAPI
from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    HttpUrl,
    TypeAdapter,
    ValidationError,
)
from simcore_service_api_server.models._utils_pydantic import UriSchema


class _FakeModel(BaseModel):
    urls0: list[HttpUrl]
    urls1: list[Annotated[HttpUrl, UriSchema()]]

    # with and w/o
    url0: HttpUrl
    url1: Annotated[HttpUrl, UriSchema()]

    # # including None inside/outside annotated
    url2: Annotated[HttpUrl, UriSchema()] | None
    url3: Annotated[HttpUrl | None, UriSchema()]

    # # mistake
    int0: Annotated[int, UriSchema()]


@pytest.fixture
def pydantic_schema() -> dict[str, Any]:
    return _FakeModel.model_json_schema()


def test_pydantic_json_schema(pydantic_schema: dict[str, Any]):
    assert pydantic_schema["properties"] == {
        "int0": {"title": "Int0", "type": "integer"},
        "url0": {
            "format": "uri",
            "maxLength": 2083,
            "minLength": 1,
            "title": "Url0",
            "type": "string",
        },
        "url1": {
            "format": "uri",
            "maxLength": 2083,
            "minLength": 1,
            "title": "Url1",
            "type": "string",
        },
        "url2": {
            "anyOf": [
                {"format": "uri", "maxLength": 2083, "minLength": 1, "type": "string"},
                {"type": "null"},
            ],
            "title": "Url2",
        },
        "url3": {
            "anyOf": [
                {"format": "uri", "maxLength": 2083, "minLength": 1, "type": "string"},
                {"type": "null"},
            ],
            "title": "Url3",
        },
        "urls0": {
            "items": {
                "format": "uri",
                "maxLength": 2083,
                "minLength": 1,
                "type": "string",
            },
            "title": "Urls0",
            "type": "array",
        },
        "urls1": {
            "items": {
                "format": "uri",
                "maxLength": 2083,
                "minLength": 1,
                "type": "string",
            },
            "title": "Urls1",
            "type": "array",
        },
    }


@pytest.fixture
def fastapi_schema() -> dict[str, Any]:
    app = FastAPI()

    @app.get("/", response_model=_FakeModel)
    def _h():
        ...

    openapi = app.openapi()
    return openapi["components"]["schemas"][_FakeModel.__name__]


def test_fastapi_openapi_component_schemas(fastapi_schema: dict[str, Any]):

    assert fastapi_schema["properties"] == {
        "int0": {"title": "Int0", "type": "integer"},
        "url0": {"title": "Url0", "type": "string"},
        "url1": {
            "format": "uri",
            "maxLength": 2083,
            "minLength": 1,
            "title": "Url1",
            "type": "string",
        },
        "url2": {
            "anyOf": [
                {"format": "uri", "maxLength": 2083, "minLength": 1, "type": "string"},
                {"type": "null"},
            ],
            "title": "Url2",
        },
        "url3": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Url3"},
        "urls0": {"items": {"type": "string"}, "title": "Urls0", "type": "array"},
        "urls1": {
            "items": {
                "format": "uri",
                "maxLength": 2083,
                "minLength": 1,
                "type": "string",
            },
            "title": "Urls1",
            "type": "array",
        },
    }


@pytest.mark.xfail(
    reason=f"{pydantic.__version__=} and {fastapi.__version__=} produce different json-schemas for the same model"
)
def test_compare_pydantic_vs_fastapi_schemas(
    fastapi_schema: dict[str, Any], pydantic_schema: dict[str, Any]
):

    # NOTE @all: I cannot understand this?!
    assert fastapi_schema["properties"] == pydantic_schema["properties"]


def test_differences_between_new_pydantic_url_types():
    # SEE https://docs.pydantic.dev/2.10/api/networks/

    # | **URL**                       | **AnyUrl**  | **AnyHttpUrl**  | **HttpUrl**     |
    # |-------------------------------|-------------|-----------------|-----------------|
    # | `http://example.com`          | ✅          | ✅              | ✅              |
    # | `https://example.com/resource`| ✅          | ✅              | ✅              |
    # | `ftp://example.com`           | ✅          | ❌              | ❌              |
    # | `http://localhost`            | ✅          | ✅              | ✅              |
    # | `http://127.0.0.1`            | ✅          | ✅              | ✅              |
    # | `http://127.0.0.1:8080`       | ✅          | ✅              | ✅              |
    # | `customscheme://example.com`  | ✅          | ❌              | ❌              |

    url = "http://example.com"
    TypeAdapter(AnyUrl).validate_python(url)
    TypeAdapter(HttpUrl).validate_python(url)
    TypeAdapter(AnyHttpUrl).validate_python(url)

    url = "https://example.com/resource"
    TypeAdapter(AnyUrl).validate_python(url)
    TypeAdapter(HttpUrl).validate_python(url)
    TypeAdapter(AnyHttpUrl).validate_python(url)

    url = "ftp://example.com"
    TypeAdapter(AnyUrl).validate_python(url)
    with pytest.raises(ValidationError):
        TypeAdapter(HttpUrl).validate_python(url)
    with pytest.raises(ValidationError):
        TypeAdapter(AnyHttpUrl).validate_python(url)

    url = "http://localhost"
    TypeAdapter(AnyUrl).validate_python(url)
    TypeAdapter(HttpUrl).validate_python(url)
    TypeAdapter(AnyHttpUrl).validate_python(url)

    url = "http://127.0.0.1"
    TypeAdapter(AnyUrl).validate_python(url)
    TypeAdapter(HttpUrl).validate_python(url)
    TypeAdapter(AnyHttpUrl).validate_python(url)

    url = "http://127.0.0.1:8080"
    TypeAdapter(AnyUrl).validate_python(url)
    TypeAdapter(HttpUrl).validate_python(url)
    TypeAdapter(AnyHttpUrl).validate_python(url)

    url = "customscheme://example.com"
    TypeAdapter(AnyUrl).validate_python(url)
    with pytest.raises(ValidationError):
        TypeAdapter(HttpUrl).validate_python(url)
    with pytest.raises(ValidationError):
        TypeAdapter(AnyHttpUrl).validate_python(url)

    # examples taken from docker API
    for url in (
        "https://hub-mirror.corp.example.com:5000/",
        "https://[2001:db8:a0b:12f0::1]/",
    ):
        TypeAdapter(AnyUrl).validate_python(url)
        TypeAdapter(HttpUrl).validate_python(url)
        TypeAdapter(AnyHttpUrl).validate_python(url)
