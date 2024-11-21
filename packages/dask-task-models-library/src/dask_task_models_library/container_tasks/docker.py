from pydantic import BaseModel, ConfigDict, SecretStr


class DockerBasicAuth(BaseModel):
    server_address: str
    username: str
    password: SecretStr

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "server_address": "docker.io",
                    "username": "admin",
                    "password": "123456",
                }
            ]
        },
    )
