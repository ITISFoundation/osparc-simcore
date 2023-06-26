# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from pathlib import Path
from typing import Any, Iterable

import pytest
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError
from utils import dump_specs, is_openapi_schema, list_files_in_api_specs, load_specs

# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))

ALL_SPEC_FILES: list[str] = list_files_in_api_specs("*.json") + list_files_in_api_specs(
    "*.y*ml"
)


def _patch_node_properties(key, data):
    if key == "schema":
        schema = data["schema"]
        # remove default if there is a $ref this is broken
        all_of = schema.get("allOf", [])
        for entry in all_of:
            if "$ref" in entry:
                schema.pop("default", None)
                break


def _patch(node: Any):
    if isinstance(node, dict):
        for key in list(node.keys()):
            _patch_node_properties(key, node)

            # recursive
            if key in node:  # key could have been removed in _patch_node_properties
                _patch(node[key])

    elif isinstance(node, list):
        for value in node:
            # recursive
            _patch(value)


@pytest.fixture(scope="module")
def patch_specs_in_place(tmpdir_factory) -> Iterable[None]:
    # NOTE: this fixture below only runs once

    # NOTE: since the specs are defined in multiple files
    # the patching needs to be applied to all the files
    # The files will be restored to their original state
    # after the tests finish
    tmp_path = Path(tmpdir_factory.mktemp("backups"))
    for file in ALL_SPEC_FILES:
        # create backup of spec
        file_path = Path(file)
        backup = tmp_path / file_path.relative_to("/")
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(file_path.read_text())

        # apply patch
        spec = load_specs(file_path)
        _patch(spec)
        dump_specs(spec, file_path)

    yield

    for file in ALL_SPEC_FILES:
        # restore from backup if modified
        file_path = Path(file)
        backup = tmp_path / file_path.relative_to("/")
        if file_path.read_text() != backup.read_text():
            file_path.write_text(backup.read_text())


@pytest.mark.parametrize("spec_file", ALL_SPEC_FILES)
def test_valid_openapi_specs(patch_specs_in_place: None, spec_file: str):
    spec_file_path = Path(spec_file)
    specs = load_specs(spec_file_path)
    if is_openapi_schema(specs):
        try:
            validate_spec(specs, spec_url=spec_file_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail(f"Failed validating {spec_file_path}:\n{err.message}")
