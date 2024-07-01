from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final
from uuid import UUID

from locust import HttpUser, task
from pydantic import Field
from pydantic_settings import BaseSettings
from requests.auth import HTTPBasicAuth
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)
from urllib3 import PoolManager, Retry

_MAX_WAIT_SECONDS: Final[int] = 60


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
        self._input_json_uuid = None
        self._job_uuid = None

    def on_stop(self) -> None:
        if self._input_json_uuid is not None:
            response = self.client.delete(
                f"/v0/files/{self._input_json_uuid}", name="/v0/files/[file_id]"
            )
            response.raise_for_status()
        if self._job_uuid is not None:
            response = self.client.delete(
                f"/v0/studies/{self._user_settings.template_uuid}/jobs/{self._job_uuid}",
                name="/v0/studies/[study_id]/jobs/[job_id]",
            )
            response.raise_for_status()

    @task
    def create_and_run_job(self):
        # upload file
        with TemporaryDirectory() as tmp_dir:
            file = Path(tmp_dir) / "input.json"
            file.write_text(
                """
                {
                    "f1": 3
                }
                """
            )
            self._input_json_uuid = self.upload_file(file)

        # create job
        response = self.client.post(
            f"/v0/studies/{self._user_settings.template_uuid}/jobs",
            json={
                "values": {"InputFile1": f"{self._input_json_uuid}"},
            },
            auth=self._auth,
            name="/v0/studies/[study_id]/jobs",
        )
        response.raise_for_status()
        job_uuid = response.json().get("id")
        assert job_uuid is not None
        self._job_uuid = UUID(job_uuid)

        # start job
        response = self.client.post(
            f"/v0/studies/{self._user_settings.template_uuid}/jobs/{self._job_uuid}:start",
            auth=self._auth,
            name="/v0/studies/[study_id]/jobs/[job_id]:start",
        )
        response.raise_for_status()
        state = response.json().get("state")
        for attempt in Retrying(
            stop=stop_after_delay(timedelta(seconds=_MAX_WAIT_SECONDS)),
            wait=wait_exponential(),
            retry=retry_if_exception_type(RuntimeError),
        ):
            with attempt:
                response = self.client.post(
                    f"/v0/studies/{self._user_settings.template_uuid}/jobs/{self._job_uuid}:inspect",
                    auth=self._auth,
                    name="/v0/studies/[study_id]/jobs/[job_id]:inspect",
                )
                response.raise_for_status()
                state = response.json().get("state")
                if not state in {"SUCCESS", "FAILED"}:
                    raise RuntimeError(
                        f"Computation not finished after attempt {attempt.retry_state.attempt_number}"
                    )

        assert state == "SUCCESS"

    def upload_file(self, file: Path) -> UUID:
        assert file.is_file()
        files = {"file": open(f"{file.resolve()}", "rb")}
        response = self.client.put("/v0/files/content", files=files, auth=self._auth)
        response.raise_for_status()
        file_uuid = response.json().get("id")
        assert file_uuid is not None
        return UUID(file_uuid)
