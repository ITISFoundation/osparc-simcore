from collections import deque
from typing import Any, Deque, Dict
from uuid import UUID

from pydantic import BaseModel, Field, constr, validate_arguments

from models_library.projects import ProjectID

from .generics import DictModel
from .projects_nodes_io import NodeID

SERVICE_NETWORK_RE = r"^[a-zA-Z]([a-zA-Z0-9_-]{0,63})$"


DockerNetworkName = constr(regex=SERVICE_NETWORK_RE)
DockerNetworkAlias = constr(regex=SERVICE_NETWORK_RE)


@validate_arguments
def validate_network_name(value: DockerNetworkName) -> DockerNetworkName:
    return value


@validate_arguments
def validate_network_alias(value: DockerNetworkAlias) -> DockerNetworkAlias:
    return value


class BaseModelDict(DictModel):
    @staticmethod
    def _convert_dict_uuid_keys(dict_data: Dict[Any, Any]) -> Dict[Any, Any]:
        to_change: Deque[UUID] = deque()
        for key in dict_data.keys():
            if isinstance(key, UUID):
                to_change.append(key)

        for key in to_change:
            dict_data[f"{key}"] = dict_data.pop(key)

        return dict_data

    def _iter(self, *args, **kwargs) -> "TupleGenerator":
        # ensure dict key conversion works with either
        # .json() and .dict() methods
        for tuple_generator in super()._iter(*args, **kwargs):
            dict_key, value = tuple_generator
            if isinstance(value, dict):
                value = self._convert_dict_uuid_keys(value)
            yield dict_key, value

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        return super().dict(*args, **kwargs)["__root__"]


class ContainerAliases(BaseModelDict):
    __root__: Dict[NodeID, DockerNetworkAlias]


class NetworksWithAliases(BaseModelDict):
    __root__: Dict[DockerNetworkName, ContainerAliases]

    class Config:
        schema_extra = {
            "examples": [
                {"nSetwork_name12-s": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
                {"C": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}},
                {"shr-ntwrk_5c743ad2-8fdb-11ec-bb3a-02420a000008_default": {}},
            ],
            "invalid_examples": [
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
            ],
        }


class SharingNetworks(BaseModel):
    project_uuid: ProjectID = Field(..., description="project reference")
    networks_with_aliases: NetworksWithAliases = Field(
        ...,
        description=(
            "Networks which connect nodes from the project. Each node "
            "is given a user defined alias by which it is identified on the network."
        ),
    )

    @classmethod
    def create_empty(cls, project_uuid: ProjectID) -> "SharingNetworks":
        return cls.parse_obj(dict(project_uuid=project_uuid, networks_with_aliases={}))

    @classmethod
    def create(
        cls, project_uuid: ProjectID, networks_with_aliases: NetworksWithAliases
    ) -> "SharingNetworks":
        return cls.parse_obj(
            dict(project_uuid=project_uuid, networks_with_aliases=networks_with_aliases)
        )

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "project_uuid": "ec5cdfea-f24e-4aa1-83b8-6dccfdc8cf4d",
                "networks_with_aliases": {
                    "nSetwork_name12-s": {"5057e2c1-d392-4d31-b5c8-19f3db780390": "ok"}
                },
            }
        }
