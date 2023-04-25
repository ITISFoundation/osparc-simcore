from http import HTTPStatus
from typing import Any, Literal

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

    def __str__(self) -> str:
        return f"{self.description: self.request_desc}"

    @property
    def request_desc(self) -> str:
        return f"{self.method} {self.path}"
