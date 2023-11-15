import datetime
import tempfile
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeAlias

import sh
from aws_library.ec2.models import EC2InstanceData, EC2InstanceType, Resources
from models_library.docker import DockerGenericTag
from models_library.generated_models.docker_rest_api import Node
from pydantic import BaseModel, Extra, Field, validator


@dataclass(frozen=True, kw_only=True)
class AssignedTasksToInstance:
    instance: EC2InstanceData
    available_resources: Resources
    assigned_tasks: list


@dataclass(frozen=True, kw_only=True)
class AssignedTasksToInstanceType:
    instance_type: EC2InstanceType
    assigned_tasks: list


@dataclass(frozen=True)
class AssociatedInstance:
    node: Node
    ec2_instance: EC2InstanceData


@dataclass(frozen=True)
class Cluster:
    active_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is active (with running tasks)"
        }
    )
    drained_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is drained (with no tasks)"
        }
    )
    reserve_drained_nodes: list[AssociatedInstance] = field(
        metadata={
            "description": "This is a EC2 backed docker node which is drained in the reserve if this is enabled (with no tasks)"
        }
    )
    pending_ec2s: list[EC2InstanceData] = field(
        metadata={
            "description": "This is an EC2 instance that is not yet associated to a docker node"
        }
    )
    disconnected_nodes: list[Node] = field(
        metadata={
            "description": "This is a docker node which is not backed by a running EC2 instance"
        }
    )
    terminated_instances: list[EC2InstanceData]


DaskTaskId: TypeAlias = str
DaskTaskResources: TypeAlias = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class DaskTask:
    task_id: DaskTaskId
    required_resources: DaskTaskResources


AMIIdStr: TypeAlias = str
CommandStr: TypeAlias = str


class EC2InstanceBootSpecific(BaseModel):
    ami_id: AMIIdStr
    custom_boot_scripts: list[CommandStr] = Field(
        default_factory=list,
        description="script(s) to run on EC2 instance startup (be careful!), "
        "each entry is run one after the other using '&&' operator",
    )
    pre_pull_images: list[DockerGenericTag] = Field(
        default_factory=list,
        description="a list of docker image/tags to pull on instance cold start",
    )
    pre_pull_images_cron_interval: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=30),
        description="time interval between pulls of images (minimum is 1 minute) "
        "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    # just AMI
                    "ami_id": "ami-123456789abcdef",
                },
                {
                    # AMI + scripts
                    "ami_id": "ami-123456789abcdef",
                    "custom_boot_scripts": ["ls -tlah", "echo blahblah"],
                },
                {
                    # AMI + scripts + pre-pull
                    "ami_id": "ami-123456789abcdef",
                    "custom_boot_scripts": ["ls -tlah", "echo blahblah"],
                    "pre_pull_images": [
                        "nginx:latest",
                        "itisfoundation/my-very-nice-service:latest",
                        "simcore/services/dynamic/another-nice-one:2.4.5",
                        "asd",
                    ],
                },
                {
                    # AMI + pre-pull
                    "ami_id": "ami-123456789abcdef",
                    "pre_pull_images": [
                        "nginx:latest",
                        "itisfoundation/my-very-nice-service:latest",
                        "simcore/services/dynamic/another-nice-one:2.4.5",
                        "asd",
                    ],
                },
                {
                    # AMI + pre-pull + cron
                    "ami_id": "ami-123456789abcdef",
                    "pre_pull_images": [
                        "nginx:latest",
                        "itisfoundation/my-very-nice-service:latest",
                        "simcore/services/dynamic/another-nice-one:2.4.5",
                        "asd",
                    ],
                    "pre_pull_images_cron_interval": "01:00:00",
                },
            ]
        }

    @validator("custom_boot_scripts")
    @classmethod
    def validate_bash_calls(cls, v):
        try:
            with tempfile.NamedTemporaryFile(mode="wt", delete=True) as temp_file:
                temp_file.writelines(v)
                temp_file.flush()
                # NOTE: this will not capture runtime errors, but at least some syntax errors such as invalid quotes
                sh.bash("-n", temp_file.name)
        except sh.ErrorReturnCode as exc:
            msg = f"Invalid bash call in custom_boot_scripts: {v}, Error: {exc.stderr}"
            raise ValueError(msg) from exc

        return v
