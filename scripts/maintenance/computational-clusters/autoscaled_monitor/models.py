import datetime
import uuid
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypeAlias

import parse
from mypy_boto3_ec2 import EC2ServiceResource
from mypy_boto3_ec2.service_resource import Instance
from pydantic import BaseModel, ByteSize, PostgresDsn


@dataclass(kw_only=True, frozen=True, slots=True)
class BastionHost:
    ip: str


@dataclass(kw_only=True)
class AppState:
    environment: dict[str, str | None] = field(default_factory=dict)
    ec2_resource_autoscaling: EC2ServiceResource | None = None
    ec2_resource_clusters_keeper: EC2ServiceResource | None = None
    dynamic_parser: parse.Parser
    computational_parser_primary: parse.Parser
    computational_parser_workers: parse.Parser
    deploy_config: Path | None = None
    ssh_key_path: Path | None = None
    main_bastion_host: BastionHost | None = None

    computational_bastion: Instance | None = None
    dynamic_bastion: Instance | None = None


@dataclass(slots=True, kw_only=True)
class AutoscaledInstance:
    name: str
    ec2_instance: Instance
    disk_space: ByteSize


class InstanceRole(str, Enum):
    manager = "manager"
    worker = "worker"


@dataclass(slots=True, kw_only=True)
class ComputationalInstance(AutoscaledInstance):
    role: InstanceRole
    user_id: int
    wallet_id: int
    last_heartbeat: datetime.datetime | None
    dask_ip: str


@dataclass
class DynamicService:
    node_id: str
    user_id: int
    project_id: str
    service_name: str
    service_version: str
    created_at: datetime.datetime
    needs_manual_intervention: bool
    containers: list[str]


@dataclass(slots=True, kw_only=True)
class DynamicInstance(AutoscaledInstance):
    running_services: list[DynamicService]


TaskId: TypeAlias = str
TaskState: TypeAlias = str


@dataclass(slots=True, kw_only=True, frozen=True)
class ComputationalTask:
    project_id: uuid.UUID
    node_id: uuid.UUID
    job_id: TaskId | None
    service_name: str
    service_version: str
    state: str


@dataclass(slots=True, kw_only=True, frozen=True)
class DaskTask:
    job_id: TaskId
    state: TaskState


@dataclass(frozen=True, slots=True, kw_only=True)
class ComputationalCluster:
    primary: ComputationalInstance
    workers: list[ComputationalInstance]

    scheduler_info: dict[str, Any]
    datasets: tuple[str, ...]
    processing_jobs: dict[str, str]
    task_states_to_tasks: dict[str, list[TaskState]]


DockerContainer = namedtuple(  # noqa: PYI024
    "docker_container",
    [
        "node_id",
        "user_id",
        "project_id",
        "created_at",
        "name",
        "service_name",
        "service_version",
    ],
)


class PostgresDB(BaseModel):
    dsn: PostgresDsn
