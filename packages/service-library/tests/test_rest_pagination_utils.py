from copy import deepcopy

import pytest
from servicelib.rest_pagination_utils import PageResponseLimitOffset


def test_page_response_limit_offset_model():
    examples = PageResponseLimitOffset.Config.schema_extra["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = PageResponseLimitOffset(**example)
        assert model_instance


def test_empty_data_is_converted_to_list():
    example = deepcopy(PageResponseLimitOffset.Config.schema_extra["examples"][0])
    example["data"] = None

    model_instance = PageResponseLimitOffset(**example)
    assert model_instance
    assert model_instance.data == []


def test_more_data_than_limit_raises():
    example = deepcopy(PageResponseLimitOffset.Config.schema_extra["examples"][0])
    example["_meta"]["limit"] = len(example["data"]) - 1

    with pytest.raises(ValueError):
        PageResponseLimitOffset(**example)
