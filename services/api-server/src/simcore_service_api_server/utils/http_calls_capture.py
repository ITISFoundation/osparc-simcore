import json
from http import HTTPStatus
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field
from simcore_service_api_server.utils.http_calls_capture_processing import (
    UrlPath,
    preprocess_response,
)


class HttpApiCallCaptureModel(BaseModel):
    """
    Captures relevant information of a call to the http api
    """

    name: str
    description: str
    method: Literal["GET", "PUT", "POST", "PATCH", "DELETE"]
    host: str
    path: UrlPath
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
            host=request.url.host,
            path=url_path,
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
