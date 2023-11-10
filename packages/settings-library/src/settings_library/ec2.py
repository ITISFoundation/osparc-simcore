import datetime

from pydantic import Field

from .base import BaseCustomSettings


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: str | None = Field(
        default=None, description="do not define if using standard AWS"
    )
    EC2_REGION_NAME: str = "us-east-1"
    EC2_SECRET_ACCESS_KEY: str


class EC2InstancesSettings(BaseCustomSettings):
    EC2_INSTANCES_ALLOWED_TYPES: list[str] = Field(
        ...,
        min_items=1,
        unique_items=True,
        description="Defines which EC2 instances are considered as candidates for new EC2 instance",
    )
    EC2_INSTANCES_AMI_ID: str = Field(
        ...,
        min_length=1,
        description="Defines the AMI (Amazon Machine Image) ID used to start a new EC2 instance",
    )
    EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS: list[str] = Field(
        default_factory=list,
        description="script(s) to run on EC2 instance startup (be careful!), each entry is run one after the other using '&&' operator",
    )
    EC2_INSTANCES_KEY_NAME: str = Field(
        ...,
        min_length=1,
        description="SSH key filename (without ext) to access the instance through SSH"
        " (https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html),"
        "this is required to start a new EC2 instance",
    )
    EC2_INSTANCES_MAX_INSTANCES: int = Field(
        default=10,
        description="Defines the maximum number of instances the autoscaling app may create",
    )
    EC2_INSTANCES_NAME_PREFIX: str = Field(
        default="autoscaling",
        min_length=1,
        description="prefix used to name the EC2 instances created by this instance of autoscaling",
    )
    EC2_INSTANCES_SECURITY_GROUP_IDS: list[str] = Field(
        ...,
        min_items=1,
        description="A security group acts as a virtual firewall for your EC2 instances to control incoming and outgoing traffic"
        " (https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html), "
        " this is required to start a new EC2 instance",
    )
    EC2_INSTANCES_SUBNET_ID: str = Field(
        ...,
        min_length=1,
        description="A subnet is a range of IP addresses in your VPC "
        " (https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html), "
        "this is required to start a new EC2 instance",
    )
    EC2_INSTANCES_TIME_BEFORE_TERMINATION: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=1),
        description="Time after which an EC2 instance may be terminated (0<=T<=59 minutes, is automatically capped)"
        "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )
