from typing import Any, List

from pydantic import BaseModel, Field


class ServiceSetting(BaseModel):
    name: str = Field(..., description="The name of the service setting")
    setting_type: str = Field(
        ...,
        description="The type of the service setting (follows Docker REST API naming scheme)",
        alias="type",
    )
    value: Any = Field(
        ...,
        description="The value of the service setting (shall follow Docker REST API scheme for services",
    )


class ServiceSettings(BaseModel):
    __root__: List[ServiceSetting]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]
