import json
import random
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote
from uuid import UUID

from locust import HttpUser, task
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from requests.auth import HTTPBasicAuth
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_exponential
from urllib3 import PoolManager, Retry

# Perform the following setup in order to run this load test:
# 1. Copy .env-devel to .env in this directory and add your osparc keys to .env.
# 2. Construct a study **template** according to study_template.png. passer.py is the file next to this file.
# 3. Setup the locust settings in the .env file (see https://docs.locust.io/en/stable/configuration.html#all-available-configuration-options)
# run 'make test target=metamodeling/workflow.py' in your terminal and watch the magic happen 🤩


class UserSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    OSPARC_API_KEY: str = Field(default=...)
    OSPARC_API_SECRET: str = Field(default=...)


_SOLVER_KEY = "simcore/services/comp/osparc-python-runner"
_SOLVER_VERSION = "1.2.0"

_PYTHON_SCRIPT = """
import numpy as np
import pathlib as pl
import json

def main():

    input_json = pl.Path(os.environ["INPUT_FOLDER"]) / "function_inputs.json"
    object = json.load(input_json..read_text())
    x = object["x"]
    y = object["y"]

    return np.sinc(x) * np.sinc(y)


if __name__ == "__main__":
    main()
"""


class Schema(BaseModel):
    schema_content: dict = Field(default={})
    schema_class: str = Field(default="application/schema+json")


class Function(BaseModel):
    function_class: str = Field(default="SOLVER")
    title: str
    description: str
    input_schema: Schema = Field(default=Schema())
    output_schema: Schema = Field(default=Schema())
    default_inputs: dict[str, str] = Field(default=dict())
    solver_key: str = Field(default=_SOLVER_KEY)
    solver_version: str = Field(default=_SOLVER_VERSION)


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

        self._function_uid = None
        self._input_json_uuid = None
        self._script_uuid = None
        self._run_uid = None
        self._solver_job_uid = None

        super().__init__(*args, **kwargs)

    def on_stop(self) -> None:
        if self._script_uuid is not None:
            _ = self.client.delete(
                f"/v0/files/{self._script_uuid}",
                name="/v0/files/[file_id]",
                auth=self._auth,
            )
        if self._input_json_uuid is not None:
            _ = self.client.delete(
                f"/v0/files/{self._input_json_uuid}",
                name="/v0/files/[file_id]",
                auth=self._auth,
            )
        if self._function_uid is not None:
            _ = self.client.delete(
                f"/v0/functions/{self._function_uid}",
                name="/v0/functions/[function_uid]",
                auth=self._auth,
            )
        if self._run_uid is not None:
            _ = self.client.delete(
                f"/v0/function_jobs/{self._run_uid}",
                name="/v0/function_jobs/[function_run_uid]",
                auth=self._auth,
            )

    @task
    def run_function(self):
        with TemporaryDirectory() as tmpdir:
            tmp_dir = Path(tmpdir)
            script = tmp_dir / "script.py"
            script.write_text(_PYTHON_SCRIPT)
            self._script_uuid = self.upload_file(script)

            inputs = {"x": random.uniform(-10, 10), "y": random.uniform(-10, 10)}
            input_json = tmp_dir / "function_inputs.json"
            input_json.write_text(json.dumps(inputs))
            self._input_json_uuid = self.upload_file(input_json)

        _function = Function(
            title="Test function",
            description="Test function",
            default_inputs={"input_0": f"{self._script_uuid}"},
        )
        response = self.client.post(
            "/v0/functions", json=_function.model_dump(), auth=self._auth
        )
        response.raise_for_status()
        self._function_uid = response.json().get("uid")
        assert self._function_uid is not None

        response = self.client.post(
            f"/v0/functions/{self._function_uid}:run",
            json={"input_1": f"{self._input_json_uuid}"},
            auth=self._auth,
            name="/v0/functions/[function_uid]:run",
        )
        response.raise_for_status()
        self._run_uid = response.json().get("uid")
        assert self._run_uid is not None
        self._solver_job_uid = response.json().get("solver_job_id")
        assert self._solver_job_uid is not None

        self.wait_until_done()

        response = self.client.get(
            f"/v0/solvers/{quote(_SOLVER_KEY, safe='')}/releases/{_SOLVER_VERSION}/jobs/{self._solver_job_uid}/outputs",
            auth=self._auth,
            name="/v0/solvers/[solver_key]/releases/[solver_version]/jobs/[solver_job_id]/outputs",
        )
        response.raise_for_status()

    @retry(
        stop=stop_after_delay(timedelta(minutes=10)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(AssertionError),
        reraise=False,
    )
    def wait_until_done(self):
        response = self.client.get(
            f"/v0/function_jobs/{self._run_uid}/status",
            auth=self._auth,
            name="/v0/function_jobs/[function_run_uid]/status",
        )
        response.raise_for_status()
        status = response.json().get("status")
        assert status in ["DONE", "FAILED"]

    def upload_file(self, file: Path) -> UUID:
        assert file.is_file()
        with file.open(mode="rb") as f:
            files = {"file": f}
            response = self.client.put(
                "/v0/files/content", files=files, auth=self._auth
            )
            response.raise_for_status()
            file_uuid = response.json().get("id")
        assert file_uuid is not None
        return UUID(file_uuid)


if __name__ == "__main__":
    function = Function(
        title="Test function",
        description="Test function",
        default_inputs={},
    )
    print(function.model_dump_json())
