import json
from http import HTTPStatus
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx
import respx
from fastapi import status
from pydantic import BaseModel, Field

from .httpx_calls_capture_openapi import enhance_path_description_from_openapi_spec
from .httpx_calls_capture_parameters import PathDescription


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
    response_body: list[Any] | dict[str, Any] | None = None
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
            path = enhance_path_description_from_openapi_spec(response)
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


def get_captured_model(name: str, response: httpx.Response) -> HttpApiCallCaptureModel:
    return HttpApiCallCaptureModel.create_from_response(response, name=name)


class SideEffectCallback(Protocol):
    def __call__(
        self,
        request: httpx.Request,
        kwargs: dict[str, Any],
        capture: HttpApiCallCaptureModel,
    ) -> Any:
        ...


class CreateRespxMockCallback(Protocol):
    def __call__(
        self,
        respx_mocks: list[respx.MockRouter],
        capture_path: Path,
        side_effects_callbacks: list[SideEffectCallback],
    ) -> list[respx.MockRouter]:
        ...
