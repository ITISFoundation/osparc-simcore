import json
from http import HTTPStatus
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field


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

        return cls(
            name=name,
            description=description or f"{request}",
            method=request.method,
            host=request.url.host,
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

    def as_response(self) -> httpx.Response:
        return httpx.Response(status_code=self.status_code, json=self.response_body)


def get_captured_as_json(name: str, response: httpx.Response) -> str:
    capture_json: str = HttpApiCallCaptureModel.create_from_response(
        response, name=name
    ).json(indent=1)
    return f"{capture_json}"
