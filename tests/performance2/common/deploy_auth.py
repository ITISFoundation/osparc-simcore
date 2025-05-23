from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MonitoringBasicAuth(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    SC_USER_NAME: str = Field(default=..., examples=["<your username>"])
    SC_PASSWORD: str = Field(default=..., examples=["<your password>"])

    def to_auth(self) -> tuple[str, str]:
        return (self.SC_USER_NAME, self.SC_PASSWORD)
