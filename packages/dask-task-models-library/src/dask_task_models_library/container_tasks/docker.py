from pydantic import BaseModel, Extra, SecretStr


class DockerBasicAuth(BaseModel):
    server_address: str
    username: str
    password: SecretStr

    class Config:
        extra = Extra.forbid
        schema_extra = {
            "examples": [
                {
                    "server_address": "docker.io",
                    "username": "admin",
                    "password": "123456",
                }
            ]
        }
