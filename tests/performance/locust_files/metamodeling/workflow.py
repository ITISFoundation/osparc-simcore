from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final
from uuid import UUID

from locust import HttpUser, task
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.auth import HTTPBasicAuth
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)
from urllib3 import PoolManager, Retry

_MAX_WAIT_SECONDS: Final[int] = 60


# Perform the following setup in order to run this load test:
# 1. Copy .env-devel to .env in this directory and add your osparc keys to .env.
# 2. Construct a study **template** according to study_template.png. passer.py is the file next to this file.
# 3. Setup the locust settings in the .env file (see https://docs.locust.io/en/stable/configuration.html#all-available-configuration-options)
# run 'make test target=metamodeling/workflow.py' in your terminal and watch the magic happen 🤩


class UserSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    OSPARC_API_KEY: str = Field(default=...)
    OSPARC_API_SECRET: str = Field(default=...)

    TEMPLATE_UUID: UUID = Field(
        default=..., examples=["2ed6b0a1-f1a8-4495-8d65-d516f58b7ae0"]
    )


class MetaModelingUser(HttpUser):
    def __init__(self, *args, **kwargs):
        self._user_settings = UserSettings()
        self._auth = HTTPBasicAuth(
            username=self._user_settings.OSPARC_API_KEY,
            password=self._user_settings.OSPARC_API_SECRET,
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

        self._input_json_uuid = None
        self._job_uuid = None

        super().__init__(*args, **kwargs)

    def on_start(self) -> None:
        self.client.get("/v0/me", auth=self._auth)  # fail fast

    def on_stop(self) -> None:
        if self._input_json_uuid is not None:
            response = self.client.delete(
                f"/v0/files/{self._input_json_uuid}", name="/v0/files/[file_id]"
            )
            response.raise_for_status()
        if self._job_uuid is not None:
            response = self.client.delete(
                f"/v0/studies/{self._user_settings.TEMPLATE_UUID}/jobs/{self._job_uuid}",
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
            f"/v0/studies/{self._user_settings.TEMPLATE_UUID}/jobs",
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
            f"/v0/studies/{self._user_settings.TEMPLATE_UUID}/jobs/{self._job_uuid}:start",
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
                    f"/v0/studies/{self._user_settings.TEMPLATE_UUID}/jobs/{self._job_uuid}:inspect",
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

        response = self.client.post(
            f"/v0/studies/{self._user_settings.TEMPLATE_UUID}/jobs/{self._job_uuid}/outputs",
            auth=self._auth,
            name="/v0/studies/[study_id]/jobs/[job_id]/outputs",
        )
        response.raise_for_status()
        results = response.json()
        assert results is not None
        output_file = results.get("OutputFile1")
        assert output_file is not None
        output_file_uuid = output_file.get("id")
        assert output_file_uuid is not None

    def upload_file(self, file: Path) -> UUID:
        assert file.is_file()
        with open(f"{file.resolve()}", "rb") as f:
            files = {"file": f}
            response = self.client.put(
                "/v0/files/content", files=files, auth=self._auth
            )
            response.raise_for_status()
            file_uuid = response.json().get("id")
        assert file_uuid is not None
        return UUID(file_uuid)
