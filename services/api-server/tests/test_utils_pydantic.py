# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
from simcore_service_api_server.models._utils_pydantic import UriSchema
from simcore_service_api_server.models.schemas.files import FileUploadData


def test_it():

    schema = FileUploadData.model_json_schema()
    assert schema["properties"]["urls"]


def test_annotated_url_in_pydantic_changes_in_fastapi():
    class TestModel(BaseModel):
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

    pydantic_schema = TestModel.model_json_schema()

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

    app = FastAPI()

    @app.get("/", response_model=TestModel)
    def _h():
        ...

    openapi = app.openapi()
    fastapi_schema = openapi["components"]["schemas"]["TestModel"]

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

    # NOTE @all: I cannot understand this?!
    assert fastapi_schema["properties"] != pydantic_schema["properties"]
