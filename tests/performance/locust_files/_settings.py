from locust_settings import LocustSettings
from pydantic import Field


class LoadTestSettings(LocustSettings):
    SC_USER_NAME: str = Field(default=..., examples=["<username>"])
    SC_PASSWORD: str = Field(default=..., examples=["<password>"])


if __name__ == "__main__":
    print(LoadTestSettings().model_dump_json())
