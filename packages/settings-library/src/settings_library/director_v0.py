from functools import cached_property

from pydantic import AnyHttpUrl, Field, TypeAdapter
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag


class DirectorV0Settings(BaseCustomSettings):
    DIRECTOR_ENABLED: bool = True

    DIRECTOR_HOST: str = "director"
    DIRECTOR_PORT: PortInt = TypeAdapter(PortInt).validate_python(8000)
    DIRECTOR_VTAG: VersionTag = Field(
        default="v0", description="Director-v0 service API's version tag"
    )

    @cached_property
    def endpoint(self) -> str:
        url = AnyHttpUrl.build(  # pylint: disable=no-member
            scheme="http",
            host=self.DIRECTOR_HOST,
            port=self.DIRECTOR_PORT,
            path=f"{self.DIRECTOR_VTAG}",
        )
        return f"{url}"
