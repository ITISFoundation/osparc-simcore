import json
from http import HTTPStatus
from typing import Any, Literal

import httpx
from pydantic import BaseModel


class HttpApiCallCaptureModel(BaseModel):
    """
    Captures relevant information of a call to the http api
    """

    name: str
    description: str
    method: Literal["GET", "PUT", "POST", "PATCH", "DELETE"]
    path: str
    query: str | None = None
    request_payload: dict[str, Any] | None = None
    response_body: dict[str, Any] | None = None
    status_code: HTTPStatus = HTTPStatus.OK

    @classmethod
    def create_from_response(
        cls, response: httpx.Response, name: str, description: str = ""
    ) -> "HttpApiCallCaptureModel":
        request = response.request
        return cls(
            name=name,
            description=description or f"{request}",
            method=request.method,
            path=request.url.path,
            query=request.url.query.decode() or None,
            request_payload=json.loads(request.content.decode())
            if request.content
            else None,
            response_body=response.json(),
            status_code=response.status_code,
        )

    def __str__(self) -> str:
        return f"{self.description: self.request_desc}"

    @property
    def request_desc(self) -> str:
        return f"{self.method} {self.path}"
