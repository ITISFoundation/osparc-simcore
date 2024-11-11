from copy import deepcopy

import pytest
from models_library.rest_pagination import Page, PageMetaInfoLimitOffset
from pydantic.main import BaseModel
from pytest_simcore.examples.models_library import PAGE_EXAMPLES


@pytest.mark.parametrize(
    "cls_model, examples",
    [
        (Page[str], PAGE_EXAMPLES),
        (
            PageMetaInfoLimitOffset,
            PageMetaInfoLimitOffset.model_config["json_schema_extra"]["examples"],
        ),
    ],
)
def test_page_response_limit_offset_models(cls_model: BaseModel, examples: list[dict]):

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = cls_model(**example)
        assert model_instance


def test_invalid_offset():
    with pytest.raises(ValueError):
        PageMetaInfoLimitOffset(limit=6, total=5, offset=5, count=2)


@pytest.mark.parametrize(
    "count, offset",
    [
        pytest.param(7, 0, id="count bigger than limit"),
        pytest.param(6, 0, id="count bigger than total"),
        pytest.param(5, 1, id="count + offset bigger than total"),
    ],
)
def test_invalid_count(count: int, offset: int):
    with pytest.raises(ValueError):
        PageMetaInfoLimitOffset(limit=6, total=5, offset=offset, count=count)


def test_data_size_does_not_fit_count():
    example = deepcopy(PAGE_EXAMPLES[0])
    example["_meta"]["count"] = len(example["data"]) - 1
    with pytest.raises(ValueError):
        Page[str](**example)


def test_empty_data_is_converted_to_list():
    example = deepcopy(PAGE_EXAMPLES[0])
    example["data"] = None
    example["_meta"]["count"] = 0
    model_instance = Page[str](**example)
    assert model_instance
    assert model_instance.data == []
