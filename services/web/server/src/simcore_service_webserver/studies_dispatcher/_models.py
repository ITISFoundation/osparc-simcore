from typing import Annotated

from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel, Field, HttpUrl, PositiveInt


class ServiceInfo(BaseModel):
    key: ServiceKey
    version: ServiceVersion

    label: Annotated[str, Field(description="Display name")]

    thumbnail: HttpUrl = HttpUrl("https://via.placeholder.com/170x120.png")

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

    filetype: Annotated[str, Field(description="Filetype associated to this viewer")]

    input_port_key: Annotated[
        str,
        Field(description="Name of the connection port, since it is service-dependent"),
    ]


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
