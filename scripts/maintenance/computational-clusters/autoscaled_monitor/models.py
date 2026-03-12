import datetime
import uuid
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import parse
from mypy_boto3_ec2 import EC2ServiceResource
from mypy_boto3_ec2.service_resource import Instance
from pydantic import BaseModel, ByteSize, PostgresDsn


@dataclass(kw_only=True, frozen=True, slots=True)
class BastionHost:
    ip: str
    user_name: str


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


@dataclass(frozen=True, slots=True, kw_only=True)
class DiskUsage:
    mount_point: str
    free: ByteSize
    total: ByteSize


@dataclass(slots=True, kw_only=True)
class AutoscaledInstance:
    name: str
    ec2_instance: Instance
    disk_usage: list[DiskUsage] = field(default_factory=list)
    is_warm_buffer: bool = False


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
    product_name: str
    simcore_user_agent: str


@dataclass(slots=True, kw_only=True)
class DynamicInstance(AutoscaledInstance):
    running_services: list[DynamicService]


@dataclass(frozen=True, slots=True, kw_only=True)
class DynamicServiceExtraInfo:
    email: str | None = None
    wallet_id: int | None = None
    wallet_name: str | None = None
    tracker_run: "ResourceTrackerServiceRun | None" = None
    usd_per_credit: float | None = None


type TaskId = str
type TaskState = str


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
    processing_jobs: dict[str, list[str]]
    task_states_to_tasks: dict[TaskState, list[TaskId]]
    task_resources: dict[str, dict[str, Any]]  # resource_restrictions per job_id
    task_worker_states: dict[str, str]  # job_id -> worker-level state (executing/constrained/long-running)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResourceTrackerServiceRun:
    service_run_id: str
    user_id: int
    wallet_id: int | None
    product_name: str
    project_id: str
    node_id: str
    service_key: str
    service_version: str
    started_at: datetime.datetime
    last_heartbeat_at: datetime.datetime
    missed_heartbeat_counter: int
    pricing_unit_cost: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskReconciliationRow:
    job_id: TaskId
    dask_state: TaskState
    worker_state: str  # worker-level state: executing, constrained, queued, etc.
    comp_task: "ComputationalTask | None"
    tracker_run: ResourceTrackerServiceRun | None
    required_resources: dict[str, Any]
    issues: list[str]

    @property
    def is_actively_executing(self) -> bool:
        """True when the task is actually running on a thread (not just queued/constrained)."""
        return self.worker_state in {"executing", "long-running"}


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
        "product_name",
        "simcore_user_agent",
    ],
)


class PostgresDB(BaseModel):
    dsn: PostgresDsn
