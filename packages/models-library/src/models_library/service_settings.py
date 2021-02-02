from typing import Any, List

from pydantic import BaseModel, Extra, Field


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

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "examples": [
                # constraints
                {
                    "name": "constraints",
                    "type": "string",
                    "value": ["node.platform.os == linux"],
                },
                # resources
                {
                    "name": "Resources",
                    "type": "Resources",
                    "value": {
                        "Limits": {"NanoCPUs": 4000000000, "MemoryBytes": 17179869184},
                        "Reservations": {
                            "NanoCPUs": 100000000,
                            "MemoryBytes": 536870912,
                            "GenericResources": [
                                {"DiscreteResourceSpec": {"Kind": "VRAM", "Value": 1}}
                            ],
                        },
                    },
                },
                # mounts
                {
                    "name": "mount",
                    "type": "object",
                    "value": [
                        {
                            "ReadOnly": True,
                            "Source": "/tmp/.X11-unix",
                            "Target": "/tmp/.X11-unix",
                            "Type": "bind",
                        }
                    ],
                },
                # environments
                {"name": "env", "type": "string", "value": ["DISPLAY=:0"]},
            ]
        }


class ServiceSettings(BaseModel):
    __root__: List[ServiceSetting]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]
