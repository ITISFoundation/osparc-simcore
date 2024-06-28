from locust import HttpUser, task
from pydantic import Field
from pydantic_settings import BaseSettings
from requests.auth import HTTPBasicAuth
from urllib3 import PoolManager, Retry


class UserSettings(BaseSettings):
    username: str = Field(default=...)
    password: str = Field(default=...)


class MetaModelingUser(HttpUser):
    def __init__(self, *args, **kwargs):
        config = UserSettings()
        self._auth = HTTPBasicAuth(username=config.username, password=config.password)
        retry_strategy = Retry(
            total=4,
            backoff_factor=4.0,
            status_forcelist={429, 503, 504},
            allowed_methods={
                "DELETE",
                "GET",
                "HEAD",
                "OPTIONS",
                "PUT",
                "TRACE",
                "POST",
                "PATCH",
                "CONNECT",
            },
            respect_retry_after_header=True,
            raise_on_status=True,
        )
        super().__init__(
            *args, **kwargs, pool_manager=PoolManager(key_retries=retry_strategy)
        )

    def on_start(self) -> None:
        response = self.client.get("/v0/me", auth=self._auth)
        response.raise_for_status()

    @task
    def create_and_run_job(self):
        self.client.get("/v0/me", auth=self._auth)
