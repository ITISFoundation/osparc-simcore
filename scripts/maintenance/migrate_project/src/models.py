import json
from pathlib import Path
from uuid import UUID

import typer
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from settings_library.r_clone import S3Provider

_SETTINGS_EXAMPLE = {
    "source": {
        "db": {"address": "", "user": "", "password": "", "database": ""},
        "s3": {
            "endpoint": "",
            "provider": "AWS",
            "access_key": "",
            "secret_key": "",
            "bucket": "",
        },
        "project_uuid": UUID(int=0),
        "hidden_projects_for_user": None,
    },
    "destination": {
        "db": {"address": "", "user": "", "password": "", "database": ""},
        "s3": {
            "endpoint": "",
            "provider": "AWS",
            "access_key": "",
            "secret_key": "",
            "bucket": "",
        },
        "user_id": 0,
        "user_gid": 0,
    },
}


class DBConfig(BaseModel):
    address: str
    user: str
    password: SecretStr
    database: str


class S3Config(BaseModel):
    endpoint: str = "https://s3.amazonaws.com"
    provider: S3Provider = Field(
        ...,
        description='The S3 implementation / provider. Allowed values: "MINIO","CEPH","AWS"',
    )
    access_key: str
    secret_key: SecretStr
    bucket: str = Field(
        ...,
        description="S3 Bucket Name",
    )


class SourceConfig(BaseModel):
    db: DBConfig
    s3: S3Config
    project_uuid: UUID = Field(..., description="project to be moved from the source")
    hidden_projects_for_user: int | None = Field(
        None,
        description="by default nothing is moved, must provide an user ID for which to move the hidden projects",
    )


class DestinationConfig(BaseModel):
    db: DBConfig
    s3: S3Config
    user_id: int = Field(
        ...,
        description="new projects owner under which to save files and projects",
    )
    user_gid: int = Field(
        ...,
        description="group id for the user, required to give the correct permissions to the user",
    )


class Settings(BaseModel):
    source: SourceConfig
    destination: DestinationConfig

    model_config = ConfigDict(json_schema_extra={"example": _SETTINGS_EXAMPLE})

    @classmethod
    def load_from_file(cls, path: Path) -> "Settings":
        return cls.model_validate(json.loads(path.read_text()))


if __name__ == "__main__":
    # produces an empty configuration to be saved as starting point
    typer.echo(Settings.model_validate(_SETTINGS_EXAMPLE).model_dump_json(indent=2))
