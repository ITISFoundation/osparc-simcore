from typing import Dict
from .projects_nodes_io import NodeID
from pydantic import constr, BaseModel

SERVICE_NETWORK_RE = r"^[a-zA-Z]([a-zA-Z0-9_-]{0,63})$"

ServiceNetworkName = constr(regex=SERVICE_NETWORK_RE)


class SharingNetworks(BaseModel):
    __root__: Dict[ServiceNetworkName, Dict[NodeID, str]]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    class Config:
        schema_extra = {
            "examples": [
                # valid identifiers
                {"nSetwork_name12-s": {"5057e2c1-d392-4d31-b5c8-19f3db780390": ""}},
                {"C": {"5057e2c1-d392-4d31-b5c8-19f3db780390": ""}},
                # invalid identifiers
                {
                    "1_NO_START_WITH_NUMBER": {
                        "5057e2c1-d392-4d31-b5c8-19f3db780390": ""
                    }
                },
                {"_NO_UNDERSCORE_START": {"5057e2c1-d392-4d31-b5c8-19f3db780390": ""}},
                {"-NO_DASH_START": {"5057e2c1-d392-4d31-b5c8-19f3db780390": ""}},
                {
                    "MAX_64_CHARS_ALLOWED_DUE_TO_DOCKER_NETWORK_LIMITATIONS___________": {
                        "5057e2c1-d392-4d31-b5c8-19f3db780390": ""
                    }
                },
                {"i_am_ok": {"NOT_A_VALID_UUID": ""}},
            ]
        }

    # we can now have examples and tests here
    # let us put some of those
