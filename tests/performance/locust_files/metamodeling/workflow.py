from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from locust import HttpUser, task
from pydantic import Field
from pydantic_settings import BaseSettings
from requests.auth import HTTPBasicAuth
from urllib3 import PoolManager, Retry


class UserSettings(BaseSettings):
    osparc_api_key: str = Field(default=...)
    osparc_api_secret: str = Field(default=...)

    template_uuid: UUID = Field(default=...)


class MetaModelingUser(HttpUser):
    def __init__(self, *args, **kwargs):
        self._user_settings = UserSettings()
        self._auth = HTTPBasicAuth(
            username=self._user_settings.osparc_api_key,
            password=self._user_settings.osparc_api_secret,
        )
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
        self.pool_manager = PoolManager(retries=retry_strategy)

        super().__init__(*args, **kwargs)

    def on_start(self) -> None:
        self.client.get("/v0/me", auth=self._auth)  # fail fast

    @task
    def create_and_run_job(self):
        with TemporaryDirectory() as tmp_dir:
            file = Path(tmp_dir) / "input.json"
            file.write_text(
                """
                {
                    "f1": 3
                }
                """
            )
            input_file_uuid = self.upload_file(file)

        response = self.client.post(
            f"/v0/studies/{self._user_settings.template_uuid}/jobs",
            json={
                "values": {"InputFile1": f"{input_file_uuid}"},
            },
            auth=self._auth,
        )
        response.raise_for_status()

    def upload_file(self, file: Path) -> UUID:
        assert file.is_file()
        files = {"file": open(f"{file.resolve()}", "rb")}
        response = self.client.put("/v0/files/content", files=files, auth=self._auth)
        response.raise_for_status()
        file_uuid = response.json().get("id")
        assert file_uuid is not None
        return UUID(file_uuid)
