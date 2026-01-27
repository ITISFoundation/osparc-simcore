import urllib.parse
from typing import TypeAlias

from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel, ConfigDict, field_validator

from ..._models import FileParams, ServiceParams, ViewerInfo


class ServiceQueryParams(ServiceParams):
    model_config = ConfigDict(extra="forbid")


class FileQueryParams(FileParams):
    model_config = ConfigDict(extra="forbid")

    @field_validator("file_type")
    @classmethod
    def _ensure_extension_upper_and_dotless(cls, v):
        # NOTE: see filetype constraint-check
        if v and isinstance(v, str):
            w = urllib.parse.unquote(v)
            return w.upper().lstrip(".")
        return v


class ServiceAndFileParams(FileQueryParams, ServiceParams): ...


class ViewerQueryParams(BaseModel):
    file_type: str | None = None
    viewer_key: ServiceKey
    viewer_version: ServiceVersion

    @staticmethod
    def from_viewer(viewer: ViewerInfo) -> "ViewerQueryParams":
        # can safely construct w/o validation from a viewer
        return ViewerQueryParams.model_construct(
            file_type=viewer.filetype,
            viewer_key=viewer.key,
            viewer_version=viewer.version,
        )

    @field_validator("file_type")
    @classmethod
    def _ensure_extension_upper_and_dotless(cls, v):
        # NOTE: see filetype constraint-check
        if v and isinstance(v, str):
            w = urllib.parse.unquote(v)
            return w.upper().lstrip(".")
        return v


RedirectionQueryParams: TypeAlias = (
    # NOTE: Extra.forbid in FileQueryParams, ServiceQueryParams avoids bad casting when
    # errors in ServiceAndFileParams
    ServiceAndFileParams | FileQueryParams | ServiceQueryParams
)
