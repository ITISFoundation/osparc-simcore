from typing import Annotated

from aiopg.sa.result import RowProxy
from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel, Field, HttpUrl, PositiveInt, TypeAdapter


class ServiceInfo(BaseModel):
    key: ServiceKey
    version: ServiceVersion

    label: Annotated[str, Field(..., description="Display name")]

    thumbnail: HttpUrl = Field(
        default=TypeAdapter(HttpUrl).validate_python(
            "https://via.placeholder.com/170x120.png"
        )
    )

    is_guest_allowed: bool = True

    @property
    def footprint(self) -> str:
        return f"{self.key}:{self.version}"

    @property
    def title(self) -> str:
        """human readable title"""
        return f"{self.label.capitalize()} v{self.version}"


class ViewerInfo(ServiceInfo):
    """
    Here a viewer denotes a service
      - that supports (i.e. can consume) a specific filetype and
      - that is available to everyone
    and therefore it can be dispatched to both guest and active users
    to visualize a file of that type
    """

    filetype: str = Field(..., description="Filetype associated to this viewer")

    input_port_key: str = Field(
        ...,
        description="Name of the connection port, since it is service-dependent",
    )

    @classmethod
    def create_from_db(cls, row: RowProxy) -> "ViewerInfo":
        return cls(
            key=row["service_key"],
            version=row["service_version"],
            filetype=row["filetype"],
            label=row["service_display_name"] or row["service_key"].split("/")[-1],
            input_port_key=row["service_input_port"],
            is_guest_allowed=row["is_guest_allowed"],
        )


class ServiceParams(BaseModel):
    viewer_key: ServiceKey
    viewer_version: ServiceVersion

    @property
    def footprint(self) -> str:
        return f"{self.viewer_key}:{self.viewer_version}"


class FileParams(BaseModel):
    file_type: str
    file_name: str = "unknown"
    file_size: PositiveInt
    download_link: HttpUrl

    @property
    def footprint(self) -> str:
        """Identifier used to create UUID"""
        return f"{self.file_name}:{self.file_type}:{self.file_size}"
