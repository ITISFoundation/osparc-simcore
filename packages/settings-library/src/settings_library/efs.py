from pathlib import Path

from pydantic import Field

from .base import BaseCustomSettings


class AwsEfsSettings(BaseCustomSettings):
    EFS_DNS_NAME: str = Field(
        description="AWS Elastic File System DNS name",
        example="fs-xxx.efs.us-east-1.amazonaws.com",
    )
    EFS_PROJECT_SPECIFIC_DATA_DIRECTORY: str = Field(default="project-specific-data")
    EFS_MOUNTED_PATH: Path = Field(
        default=Path("/data/efs"),
        description="This is the path where EFS is mounted to the EC2 machine",
    )
    EFS_ENABLED_FOR_USERS: list[int] = Field(
        description="This is temporary solution so we can enable it for specific users for testing purpose",
        example=[1],
    )
