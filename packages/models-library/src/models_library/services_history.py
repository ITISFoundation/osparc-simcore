from datetime import date

from pydantic import BaseModel, Field


class Component(BaseModel):
    name: str
    version: str


class ServiceRelease(BaseModel):
    version: str
    release_date: date
    components: list[Component]


class Compatibility(BaseModel):
    compatible_with: list[str]


class Service(BaseModel):
    name: str
    version: str
    version_display: str = Field(
        ...,
        description="A user-friendly or marketing name for the release. This can be used to reference the release in a more readable and recognizable format, such as 'Blue Release,' 'Spring Update,' or 'Holiday Edition.' This name is not used for version comparison but is useful for communication and documentation purposes.",
    )
    release_date: date = Field(
        ...,
        description="The date when the specific version of the service was released. This field helps in tracking the timeline of releases and understanding the sequence of updates. The date should be formatted in YYYY-MM-DD format for consistency and easy sorting.",
    )
    components: list[Component]
    history: list[ServiceRelease]
    compatibility: Compatibility
