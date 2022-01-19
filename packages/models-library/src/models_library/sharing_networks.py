from typing import Dict

from pydantic import BaseModel, constr

from .projects_nodes_io import NodeID

SERVICE_NETWORK_RE = r"^[a-zA-Z]([a-zA-Z0-9_-]{0,63})$"


DockerNetworkName = constr(regex=SERVICE_NETWORK_RE)
DockerNetworkAlias = constr(regex=SERVICE_NETWORK_RE)


def validate_network_name(value: str) -> DockerNetworkName:
    class ValidationModel(BaseModel):
        item: DockerNetworkName

    return ValidationModel(item=value).item


def validate_network_alias(value: str) -> DockerNetworkAlias:
    class ValidationModel(BaseModel):
        item: DockerNetworkAlias

    return ValidationModel(item=value).item


class SharingNetworks(BaseModel):
    __root__: Dict[DockerNetworkName, Dict[NodeID, DockerNetworkAlias]]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    class Config:
        schema_extra = {
            "examples": [
                # valid identifiers
                {"nSetwork_name12-s": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
                {"C": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
                # invalid identifiers
                {
                    "1_NO_START_WITH_NUMBER": {
                        "5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"
                    }
                },
                {
                    "_NO_UNDERSCORE_START": {
                        "5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"
                    }
                },
                {"-NO_DASH_START": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
                {
                    "MAX_64_CHARS_ALLOWED_DUE_TO_DOCKER_NETWORK_LIMITATIONS___________": {
                        "5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"
                    }
                },
                {"i_am_ok": {"NOT_A_VALID_UUID": "ok"}},
                {"i_am_ok": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "1_I_AM_INVALID"}},
            ]
        }

    # we can now have examples and tests here
    # let us put some of those
