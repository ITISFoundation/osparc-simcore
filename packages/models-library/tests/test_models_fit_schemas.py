# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import json
from typing import Callable

import pytest
from pydantic.main import BaseModel

from models_library.projects import Project
from models_library.services import ServiceDockerData


@pytest.mark.parametrize(
    "pydantic_model, original_json_schema",
    [(ServiceDockerData, "node-meta-v0.0.1.json"), (Project, "project-v0.0.1.json")],
)
def test_generated_schema_same_as_original(
    pydantic_model: BaseModel,
    original_json_schema: str,
    diff_json_schemas: Callable,
    json_schema_dict: Callable,
):
    generated_schema = json.loads(pydantic_model.schema_json(indent=2))
    original_schema = json_schema_dict(original_json_schema)

    # run one direction original schema encompass generated one
    process_completion = diff_json_schemas(original_schema, generated_schema)

    assert (
        process_completion.returncode == 0
    ), f"Exit code {process_completion.returncode}\n{process_completion.stdout.decode('utf-8')}"

    # https://www.npmjs.com/package/json-schema-diff returns true (at least in WSL whatever the result)
    # ```false``` is returned at the end of the stdout
    assert "No differences found" in process_completion.stdout.decode(
        "utf-8"
    ), process_completion.stdout.decode("utf-8")

    # run other way direction:  generated one encompass original schema
    process_completion = diff_json_schemas(original_schema, generated_schema)

    assert (
        process_completion.returncode == 0
    ), f"Exit code {process_completion.returncode}\n{process_completion.stdout.decode('utf-8')}"

    # https://www.npmjs.com/package/json-schema-diff returns true (at least in WSL whatever the result)
    # ```false``` is returned at the end of the stdout
    assert "No differences found" in process_completion.stdout.decode(
        "utf-8"
    ), process_completion.stdout.decode("utf-8")
