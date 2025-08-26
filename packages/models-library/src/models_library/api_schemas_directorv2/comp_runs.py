from datetime import datetime
from typing import Any, NamedTuple

from models_library.computations import CollectionRunID
from models_library.services_types import ServiceRunID
from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    PositiveInt,
)

from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..projects_state import RunningState


class ComputationRunRpcGet(BaseModel):
    project_uuid: ProjectID
    iteration: int
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "project_uuid": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                    "iteration": 1,
                    "state": "SUCCESS",
                    "info": {
                        "wallet_id": 9866,
                        "user_email": "test@example.net",
                        "wallet_name": "test",
                        "product_name": "osparc",
                        "project_name": "test",
                        "project_metadata": {
                            "parent_node_id": "12e0c8b2-bad6-40fb-9948-8dec4f65d4d9",
                            "parent_node_name": "UJyfwFVYySnPCaLuQIaz",
                            "parent_project_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                            "parent_project_name": "qTjDmYPxeqAWfCKCQCYF",
                            "root_parent_node_id": "37176e84-d977-4993-bc49-d76fcfc6e625",
                            "root_parent_node_name": "UEXExIZVPeFzGRmMglPr",
                            "root_parent_project_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                            "root_parent_project_name": "FuDpjjFIyeNTWRUWCuKo",
                        },
                        "node_id_names_map": {},
                        "simcore_user_agent": "agent",
                    },
                    "submitted_at": "2023-01-11 13:11:47.293595",
                    "started_at": "2023-01-11 13:11:47.293595",
                    "ended_at": "2023-01-11 13:11:47.293595",
                }
            ]
        }
    )


class ComputationRunRpcGetPage(NamedTuple):
    items: list[ComputationRunRpcGet]
    total: PositiveInt


class ComputationCollectionRunRpcGet(BaseModel):
    collection_run_id: CollectionRunID
    project_ids: list[str]
    state: RunningState
    info: dict[str, Any]
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "collection_run_id": "12e0c8b2-bad6-40fb-9948-8dec4f65d4d9",
                    "project_ids": ["beb16d18-d57d-44aa-a638-9727fa4a72ef"],
                    "state": "SUCCESS",
                    "info": {
                        "wallet_id": 9866,
                        "user_email": "test@example.net",
                        "wallet_name": "test",
                        "product_name": "osparc",
                        "project_name": "test",
                        "project_metadata": {
                            "parent_node_id": "12e0c8b2-bad6-40fb-9948-8dec4f65d4d9",
                            "parent_node_name": "UJyfwFVYySnPCaLuQIaz",
                            "parent_project_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                            "parent_project_name": "qTjDmYPxeqAWfCKCQCYF",
                            "root_parent_node_id": "37176e84-d977-4993-bc49-d76fcfc6e625",
                            "root_parent_node_name": "UEXExIZVPeFzGRmMglPr",
                            "root_parent_project_id": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                            "root_parent_project_name": "FuDpjjFIyeNTWRUWCuKo",
                        },
                        "node_id_names_map": {},
                        "simcore_user_agent": "agent",
                    },
                    "submitted_at": "2023-01-11 13:11:47.293595",
                    "started_at": "2023-01-11 13:11:47.293595",
                    "ended_at": "2023-01-11 13:11:47.293595",
                }
            ]
        }
    )


class ComputationCollectionRunRpcGetPage(NamedTuple):
    items: list[ComputationCollectionRunRpcGet]
    total: PositiveInt


class ComputationTaskRpcGet(BaseModel):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    log_download_link: AnyUrl | None
    service_run_id: ServiceRunID

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "project_uuid": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                    "node_id": "12e0c8b2-bad6-40fb-9948-8dec4f65d4d9",
                    "state": "SUCCESS",
                    "progress": 0.0,
                    "image": {
                        "name": "simcore/services/comp/ti-solutions-optimizer",
                        "tag": "1.0.19",
                        "node_requirements": {"CPU": 8.0, "RAM": 25769803776},
                    },
                    "started_at": "2023-01-11 13:11:47.293595",
                    "ended_at": "2023-01-11 13:11:47.293595",
                    "log_download_link": "https://example.com/logs",
                    "service_run_id": "comp_1_12e0c8b2-bad6-40fb-9948-8dec4f65d4d9_1",
                }
            ]
        }
    )


class ComputationTaskRpcGetPage(NamedTuple):
    items: list[ComputationTaskRpcGet]
    total: PositiveInt


class ComputationCollectionRunTaskRpcGet(BaseModel):
    project_uuid: ProjectID
    node_id: NodeID
    state: RunningState
    progress: float
    image: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    log_download_link: AnyUrl | None
    service_run_id: ServiceRunID

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "project_uuid": "beb16d18-d57d-44aa-a638-9727fa4a72ef",
                    "node_id": "12e0c8b2-bad6-40fb-9948-8dec4f65d4d9",
                    "state": "SUCCESS",
                    "progress": 0.0,
                    "image": {
                        "name": "simcore/services/comp/ti-solutions-optimizer",
                        "tag": "1.0.19",
                        "node_requirements": {"CPU": 8.0, "RAM": 25769803776},
                    },
                    "started_at": "2023-01-11 13:11:47.293595",
                    "ended_at": "2023-01-11 13:11:47.293595",
                    "log_download_link": "https://example.com/logs",
                    "service_run_id": "comp_1_12e0c8b2-bad6-40fb-9948-8dec4f65d4d9_1",
                }
            ]
        }
    )


class ComputationCollectionRunTaskRpcGetPage(NamedTuple):
    items: list[ComputationCollectionRunTaskRpcGet]
    total: PositiveInt
