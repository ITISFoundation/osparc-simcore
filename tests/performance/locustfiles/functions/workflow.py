import json
import random
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Any
from urllib.parse import quote

from common.base_user import OsparcWebUserBase
from locust import run_single_user, task
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_exponential
from urllib3 import PoolManager, Retry

_SOLVER_KEY = "simcore/services/comp/osparc-python-runner"
_SOLVER_VERSION = "1.2.0"

_PYTHON_SCRIPT = """
import numpy as np
import pathlib as pl
import json
import os

def main():

    input_json = pl.Path(os.environ["INPUT_FOLDER"]) / "function_inputs.json"
    object = json.loads(input_json.read_text())
    x = object["x"]
    y = object["y"]

    return np.sinc(x) * np.sinc(y)


if __name__ == "__main__":
    main()

"""


class Schema(BaseModel):
    schema_content: dict = {}
    schema_class: str = "application/schema+json"


class Function(BaseModel):
    function_class: str = "SOLVER"
    title: str
    description: str
    input_schema: Annotated[Schema, Field()] = Schema()
    output_schema: Annotated[Schema, Field()] = Schema()
    default_inputs: Annotated[dict[str, Any], Field()] = dict()
    solver_key: Annotated[str, Field()] = _SOLVER_KEY
    solver_version: Annotated[str, Field()] = _SOLVER_VERSION


class MetaModelingUser(OsparcWebUserBase):
    # This overrides the class attribute in OsparcWebUserBase
    requires_login = True

    def __init__(self, *args, **kwargs):
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
        self._input_json = None
        self._script = None
        self._run_uid = None
        self._solver_job_uid = None

        super().__init__(*args, **kwargs)

    def on_stop(self) -> None:
        if self._script is not None:
            self.authenticated_delete(
                f"/v0/files/{self._script.get('id')}",
                name="/v0/files/[file_id]",
            )
        if self._input_json is not None:
            self.authenticated_delete(
                f"/v0/files/{self._input_json.get('id')}",
                name="/v0/files/[file_id]",
            )
        if self._function_uid is not None:
            self.authenticated_delete(
                f"/v0/functions/{self._function_uid}",
                name="/v0/functions/[function_uid]",
            )
        if self._run_uid is not None:
            self.authenticated_delete(
                f"/v0/function_jobs/{self._run_uid}",
                name="/v0/function_jobs/[function_run_uid]",
            )

    @task
    def run_function(self):
        with TemporaryDirectory() as tmpdir_str, Path(tmpdir_str) as tmpdir:
            script = tmpdir / "script.py"
            script.write_text(_PYTHON_SCRIPT)
            self._script = self.upload_file(script)

            inputs = {"x": random.uniform(-10, 10), "y": random.uniform(-10, 10)}
            input_json = tmpdir / "function_inputs.json"
            input_json.write_text(json.dumps(inputs))
            self._input_json = self.upload_file(input_json)

        _function = Function(
            title="Test function",
            description="Test function",
            default_inputs={"input_1": self._script},
        )
        response = self.authenticated_post("/v0/functions", json=_function.model_dump())
        response.raise_for_status()
        self._function_uid = response.json().get("uid")
        assert self._function_uid is not None

        response = self.authenticated_post(
            f"/v0/functions/{self._function_uid}:run",
            json={"input_2": self._input_json},
            name="/v0/functions/[function_uid]:run",
        )
        response.raise_for_status()
        self._run_uid = response.json().get("uid")
        assert self._run_uid is not None
        self._solver_job_uid = response.json().get("solver_job_id")
        assert self._solver_job_uid is not None

        self.wait_until_done()

        response = self.authenticated_get(
            f"/v0/solvers/{quote(_SOLVER_KEY, safe='')}/releases/{_SOLVER_VERSION}/jobs/{self._solver_job_uid}/outputs",
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
        response = self.authenticated_get(
            f"/v0/function_jobs/{self._run_uid}/status",
            name="/v0/function_jobs/[function_run_uid]/status",
        )
        response.raise_for_status()
        status = response.json().get("status")
        assert status in ["SUCCESS", "FAILED"]

    def upload_file(self, file: Path) -> dict[str, str]:
        assert file.is_file()
        with file.open(mode="rb") as f:
            files = {"file": f}
            response = self.authenticated_put("/v0/files/content", files=files)
            response.raise_for_status()
            assert response.json().get("id") is not None
            return response.json()


if __name__ == "__main__":
    run_single_user(MetaModelingUser)
