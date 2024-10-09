import json
from pathlib import Path
from pprint import pformat

import pytest
from cloudpickle import dumps, loads
from dask_task_models_library.container_tasks.io import (
    FilePortSchema,
    FileUrl,
    PortSchema,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from faker import Faker


@pytest.mark.parametrize(
    "model_cls",
    (
        PortSchema,
        FilePortSchema,
        FileUrl,
        TaskInputData,
        TaskOutputDataSchema,
        TaskOutputData,
    ),
)
def test_io_models_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))

        model_instance = model_cls.model_validate(example)

        assert model_instance, f"Failed with {name}"
        print(name, ":", model_instance)


def _create_fake_outputs(
    schema: TaskOutputDataSchema,
    output_folder: Path,
    set_optional_field: bool,
    faker: Faker,
) -> str | None:
    jsonable_data = {}
    for key, value in schema.items():
        if not value.required and not set_optional_field:
            continue

        if isinstance(value, FilePortSchema):
            # a file shall be present
            a_file = output_folder / (value.mapping or key)
            a_file.write_text(faker.text(max_nb_chars=450))
            assert a_file.exists()
        else:
            jsonable_data[
                key
            ] = "some value just for testing, does not represent any kind of type"
    if jsonable_data:
        output_file = output_folder / faker.file_name()
        with output_file.open("wt") as fp:
            json.dump(jsonable_data, fp)
        assert output_file.exists()
        return output_file.name
    return None


@pytest.mark.parametrize("optional_fields_set", [True, False])
def test_create_task_output_from_task_with_optional_fields_as_required(
    tmp_path: Path, optional_fields_set: bool, faker: Faker
):
    for schema_example in TaskOutputDataSchema.model_config["json_schema_extra"][
        "examples"
    ]:

        task_output_schema = TaskOutputDataSchema.model_validate(schema_example)
        outputs_file_name = _create_fake_outputs(
            task_output_schema, tmp_path, optional_fields_set, faker
        )
        task_output_data = TaskOutputData.from_task_output(
            schema=task_output_schema,
            output_folder=tmp_path,
            output_file_ext=outputs_file_name,
        )
        assert task_output_data

        for key, value in task_output_schema.items():
            if not value.required and not optional_fields_set:
                assert task_output_data.get(key) is None
            if value.required or optional_fields_set:
                assert task_output_data.get(key) is not None


def test_create_task_output_from_task_throws_when_there_are_missing_files(
    tmp_path: Path, faker: Faker
):
    task_output_schema = TaskOutputDataSchema.model_validate(
        {
            "required_file_output": {
                "required": True,
                "url": "s3://some_file_url",
                "mapping": "the_output_filename",
            },
        }
    )

    with pytest.raises(ValueError):
        TaskOutputData.from_task_output(
            schema=task_output_schema,
            output_folder=tmp_path,
            output_file_ext=faker.file_name(),
        )


def test_create_task_output_from_task_does_not_throw_when_there_are_optional_missing_files(
    tmp_path: Path, faker: Faker
):
    task_output_schema = TaskOutputDataSchema.model_validate(
        {
            "optional_file_output": {
                "required": False,
                "url": "s3://another_file_url",
                "mapping": "the_output_filename",
            },
        }
    )

    task_output_data = TaskOutputData.from_task_output(
        schema=task_output_schema,
        output_folder=tmp_path,
        output_file_ext=faker.file_name(),
    )
    assert len(task_output_data) == 0


def test_create_task_output_from_task_throws_when_there_are_entries(
    tmp_path: Path, faker: Faker
):
    task_output_schema = TaskOutputDataSchema.model_validate(
        {
            "some_output": {
                "required": True,
            },
        }
    )

    with pytest.raises(ValueError):
        TaskOutputData.from_task_output(
            schema=task_output_schema,
            output_folder=tmp_path,
            output_file_ext=faker.file_name(),
        )


def test_create_task_output_from_task_does_not_throw_when_there_are_optional_entries(
    tmp_path: Path, faker: Faker
):
    task_output_schema = TaskOutputDataSchema.model_validate(
        {
            "some_output": {
                "required": False,
            },
        }
    )

    task_output_data = TaskOutputData.from_task_output(
        schema=task_output_schema,
        output_folder=tmp_path,
        output_file_ext=faker.file_name(),
    )
    assert len(task_output_data) == 0


@pytest.mark.parametrize(
    "model_cls",
    (
        TaskInputData,
        TaskOutputDataSchema,
        TaskOutputData,
    ),
)
def test_objects_are_compatible_with_dask_requirements(model_cls, model_cls_examples):
    # NOTE: fcts could also be passed through the same test
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))

        model_instance = model_cls.model_validate(example)
        reloaded_instance = loads(dumps(model_instance))
        assert reloaded_instance == model_instance
