# fastapi.HTTPException pickles but never unpickles: it stores its state in
# attributes and leaves ``args`` empty, so pickle's default reduction rebuilds it
# with zero arguments (TypeError: missing 'status_code'). Celery tasks raising it
# (e.g. service_exception_handler) would therefore be reported through the
# degraded stand-in path in celery_library. This module adapts it to a picklable
# wire error, registered at startup (both sides need it only for full
# restoration; an unregistered consumer still receives the wire error as-is).

from typing import Any

from celery_library.errors_adapters import register_transferable_error_adapter
from common_library.errors_classes import OsparcErrorMixin
from fastapi import HTTPException


class TransferableHTTPExceptionError(OsparcErrorMixin, Exception):
    """Serializable wire error for fastapi.HTTPException"""

    # matches HTTPException.__str__ ("<status_code>: <detail>") so a consumer
    # without the from_wire adapter reports it indistinguishably from the original
    msg_template: str = "{status_code}: {detail}"

    status_code: int
    detail: Any
    headers: dict[str, str] | None

    @classmethod
    def from_http_exception(cls, error: HTTPException) -> "TransferableHTTPExceptionError":
        return cls(
            status_code=error.status_code,
            detail=error.detail,
            headers=error.headers,
        )

    def to_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=self.status_code,
            detail=self.detail,
            headers=self.headers,
        )


def register_celery_transferable_error_adapters() -> None:
    register_transferable_error_adapter(
        original_type=HTTPException,
        wire_type=TransferableHTTPExceptionError,
        to_wire=TransferableHTTPExceptionError.from_http_exception,
        from_wire=TransferableHTTPExceptionError.to_http_exception,
    )
