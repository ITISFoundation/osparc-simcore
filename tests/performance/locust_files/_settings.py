from locust_settings import LocustSettings, dump_dotenv
from pydantic import Field


class LoadTestSettings(LocustSettings):
    SC_USER_NAME: str = Field(default=..., examples=["<username>"])
    SC_PASSWORD: str = Field(default=..., examples=["<password>"])


if __name__ == "__main__":
    dump_dotenv(LoadTestSettings())
