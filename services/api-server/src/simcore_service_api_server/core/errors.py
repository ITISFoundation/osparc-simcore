from enum import auto

import httpx
from models_library.utils.enums import StrAutoEnum
from pydantic.errors import PydanticErrorMixin
from servicelib.error_codes import create_error_code
from servicelib.fastapi.httpx_utils import to_httpx_command


class _BaseAppError(PydanticErrorMixin, ValueError):
    @classmethod
    def get_full_class_name(cls) -> str:
        # Can be used as unique code identifier
        return f"{cls.__module__}.{cls.__name__}"

    def get_error_code(self):
        return create_error_code(self)


class BackendEnum(StrAutoEnum):
    CATALOG = auto()
    DIRECTOR = auto()
    STORAGE = auto()
    WEBSERVER = auto()


class BackendServiceError(_BaseAppError):
    http_status_error: httpx.HTTPStatusError | None = None
    service: BackendEnum

    msg_template = "{service} error"

    @classmethod
    def from_httpx_status_error(
        cls, error: httpx.HTTPStatusError, **ctx
    ) -> "BackendServiceError":
        return cls(http_status_error=error, service=cls.service, **ctx)

    def get_debug_message(self) -> str:
        msg = f"{self}"
        if http_status_error := getattr(self, "http_status_error", None):
            resp = http_status_error.response
            # request
            msg += f"\n\t'{to_httpx_command(http_status_error.request)}'"
            # response
            msg += f"\n\t'{resp.text}'"
            # status, latency
            msg += f"\n\t{resp.status_code}, {resp.elapsed.total_seconds()*1E6}us"
        return msg


class DirectorError(BackendServiceError):
    service = BackendEnum.DIRECTOR


class WebServerError(BackendServiceError):
    service = BackendEnum.WEBSERVER
