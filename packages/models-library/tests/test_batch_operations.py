import pytest
from faker import Faker
from models_library.api_schemas_webserver._base import (
    OutputSchema as WebServerOutputSchema,
)
from models_library.api_schemas_webserver.projects import (
    ProjectGet,
)
from models_library.batch_operations import BatchGetEnvelope, create_batch_ids_validator
from models_library.generics import Envelope
from models_library.projects import ProjectID
from pydantic import TypeAdapter, ValidationError


@pytest.mark.parametrize(
    "identifier_type,input_ids,expected_output,should_raise",
    [
        # Valid cases - successful validation
        pytest.param(
            str, ["a", "b", "c"], ["a", "b", "c"], False, id="str_valid_no_duplicates"
        ),
        pytest.param(int, [1, 2, 3], [1, 2, 3], False, id="int_valid_no_duplicates"),
        pytest.param(
            tuple,
            [("a", 1), ("b", 2)],
            [("a", 1), ("b", 2)],
            False,
            id="tuple_valid_no_duplicates",
        ),
        # Deduplication cases - preserving order
        pytest.param(
            str, ["a", "b", "a", "c"], ["a", "b", "c"], False, id="str_with_duplicates"
        ),
        pytest.param(int, [1, 2, 1, 3, 2], [1, 2, 3], False, id="int_with_duplicates"),
        pytest.param(
            tuple,
            [("a", 1), ("b", 2), ("a", 1)],
            [("a", 1), ("b", 2)],
            False,
            id="tuple_with_duplicates",
        ),
        # Single item cases
        pytest.param(str, ["single"], ["single"], False, id="str_single_item"),
        pytest.param(int, [42], [42], False, id="int_single_item"),
        # Edge case - all duplicates resolve to single item
        pytest.param(
            str, ["same", "same", "same"], ["same"], False, id="str_all_duplicates"
        ),
        # Error cases - empty list should raise ValidationError
        pytest.param(str, [], None, True, id="str_empty_list_error"),
        pytest.param(int, [], None, True, id="int_empty_list_error"),
        pytest.param(tuple, [], None, True, id="tuple_empty_list_error"),
    ],
)
def test_create_batch_ids_validator(
    identifier_type, input_ids, expected_output, should_raise
):
    validator = create_batch_ids_validator(identifier_type)

    if should_raise:
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_python(input_ids)

        # Verify the error is about minimum length
        assert "at least 1" in str(exc_info.value).lower()
    else:
        result = validator.validate_python(input_ids)
        assert result == expected_output
        assert len(result) >= 1  # Ensure minimum length constraint
        # Verify order preservation by checking first occurrence positions
        if len(set(input_ids)) != len(input_ids):  # Had duplicates
            original_first_positions = {
                item: input_ids.index(item) for item in set(input_ids)
            }
            # Items should appear in the same relative order as their first occurrence
            sorted_by_original = sorted(
                result, key=lambda x: original_first_positions[x]
            )
            assert result == sorted_by_original


def test_composing_schemas_for_batch_operations(faker: Faker):

    # inner schema model
    class WebServerProjectBatchGetSchema(
        WebServerOutputSchema, BatchGetEnvelope[ProjectGet, ProjectID]
    ): ...

    some_projects = ProjectGet.model_json_schema()["examples"]

    # response model
    response_model = Envelope[WebServerProjectBatchGetSchema].model_validate(
        {
            # NOTE: how camelcase (from WebServerOutputSchema.model_config) applies here
            "data": {
                "foundItems": some_projects,
                "missingIdentifiers": [ProjectID(faker.uuid4())],
            }
        }
    )

    assert response_model.data is not None

    assert response_model.data.found_items == TypeAdapter(
        list[ProjectGet]
    ).validate_python(some_projects)

    assert len(response_model.data.missing_identifiers) == 1
