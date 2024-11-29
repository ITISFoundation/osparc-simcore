# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
from collections.abc import Callable

import pytest
from models_library.projects import Project
from models_library.services import ServiceMetaDataPublished
from pydantic.main import BaseModel


@pytest.mark.skip(reason="waiting for PC PR")
@pytest.mark.parametrize(
    "pydantic_model, original_json_schema",
    [
        (ServiceMetaDataPublished, "node-meta-v0.0.1-pydantic.json"),
        (Project, "project-v0.0.1-pydantic.json"),
    ],
)
def test_generated_schema_same_as_original(
    pydantic_model: BaseModel,
    original_json_schema: str,
    diff_json_schemas: Callable,
    json_schema_dict: Callable,
):
    # TODO: create instead a fixture that returns a Callable and do these checks
    # on separate test_* files that follow the same package submodule's hierarchy
    #
    generated_schema = pydantic_model.model_json_schema()
    original_schema = json_schema_dict(original_json_schema)

    # NOTE: A change is considered an addition when the destination schema has become more permissive relative to the source schema. For example {"type": "string"} -> {"type": ["string", "number"]}.
    # A change is considered a removal when the destination schema has become more restrictive relative to the source schema. For example {"type": ["string", "number"]} -> {"type": "string"}.
    # The addition and removal changes detected are returned in JsonSchema format. These schemas represent the set of values that have been added or removed.

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
