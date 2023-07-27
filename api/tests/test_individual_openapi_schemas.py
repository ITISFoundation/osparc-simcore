# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
import shutil
from pathlib import Path

import pytest
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPISpecValidatorError
from utils import dump_specs, is_json_schema, is_openapi_schema, load_specs

# Conventions
_REQUIRED_FIELDS = ["error", "data"]
CONVERTED_SUFFIX = "-converted.yaml"
_FAKE_SCHEMA_NAME = "FakeSchema"

_FAKE_OPEN_API_HEADERS = {
    "openapi": "3.0.0",
    "info": {
        "title": "An include file to define sortable attributes",
        "version": "1.0.0",
    },
    "paths": {},
    "components": {"parameters": {}, "schemas": {}},
}


def add_namespace_for_converted_schemas(schema_specs: dict):
    # schemas converted from jsonschema do not have an overarching namespace.
    # the openapi validator does not like this
    # we use the jsonschema title to create a fake namespace
    fake_schema_specs = {_FAKE_SCHEMA_NAME: schema_specs}
    return fake_schema_specs


def change_references_to_schemas(filepath: Path, specs: dict):
    from os.path import abspath, exists, isabs, relpath

    filedir = filepath.parent

    for key, value in specs.items():
        if isinstance(value, dict):
            # navigate specs
            change_references_to_schemas(filepath, value)

        elif key in ("allOf", "oneOf", "anyOf"):  # navigates allOf, oneOf, anyOf
            for item in value:
                change_references_to_schemas(filepath, item)

        elif key == "$ref":
            # Ensures value = "file_ref#section_ref"
            value = str(value)
            if value.startswith("#"):
                value = str(filepath) + value
            elif "#" not in value:
                value = value + "# "

            file_ref, section_ref = value.split("#")

            if not isabs(file_ref):
                file_ref = str(filedir / file_ref)

            file_ref = abspath(file_ref)  # resolves
            assert exists(file_ref), file_ref

            if (
                "schemas" in file_ref
            ):  # reference to a schema file (i.e. inside a schemas folder)
                if not section_ref.startswith("/components/schemas/"):  # not updated!
                    section_ref = (
                        "/components/schemas/" + section_ref.lstrip("/").strip()
                    )
                    if file_ref.endswith(
                        CONVERTED_SUFFIX
                    ):  # fake name used in converted schemas
                        section_ref += _FAKE_SCHEMA_NAME

                    file_ref = (
                        "./" + relpath(file_ref, filedir)
                        if not filepath.samefile(file_ref)
                        else ""
                    )
                    specs[key] = file_ref + "#" + section_ref


@pytest.fixture(scope="session")
def converted_specs_testdir(api_specs_dir, all_api_specs_tails, tmpdir_factory):
    """
    - All api_specs files are copied into tmpdir
    - All openapi files under schemas/ folders are processed into valid openapi specs
    - All references to these files are replaced from
        $ref: ... /schemas/some_file.yaml#Reference
    to
        $ref: ... /schemas/some_file.yaml#/components/reference/Reference

    """
    basedir = api_specs_dir
    testdir = Path(tmpdir_factory.mktemp("converted-specs"))

    print(testdir)

    for tail in all_api_specs_tails:
        # directory with converted specs
        os.makedirs(testdir / tail.parent, exist_ok=True)

        specs = load_specs(basedir / tail)

        if (
            "schemas" in str(tail)
            and not is_openapi_schema(specs)
            and not is_json_schema(specs)
        ):
            # convert to valid openapi
            if tail.name.endswith(CONVERTED_SUFFIX):
                specs = add_namespace_for_converted_schemas(specs)

            new_specs = _FAKE_OPEN_API_HEADERS
            new_specs["components"]["schemas"] = specs

            # change references
            change_references_to_schemas(basedir / tail, new_specs)
            dump_specs(new_specs, testdir / tail)

        elif is_openapi_schema(specs):
            new_specs = specs
            # change references
            change_references_to_schemas(basedir / tail, new_specs)
            dump_specs(new_specs, testdir / tail)
        else:
            shutil.copy2(basedir / tail, testdir / tail)

    return testdir


@pytest.mark.skip(reason="Implementing in PR 324")
def test_valid_individual_openapi_specs(api_specs_tail, converted_specs_testdir):
    # NOTE: api_specs_tail is a parametrized **fixture**
    #
    api_specs_path = converted_specs_testdir / api_specs_tail
    try:
        specs = load_specs(api_specs_path)
        validate_spec(specs, spec_url=api_specs_path.as_uri())
    except OpenAPISpecValidatorError as err:
        pytest.fail(f"Failed validating {api_specs_path}:\n{err.message}")
