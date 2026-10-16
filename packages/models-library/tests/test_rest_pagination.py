from copy import deepcopy

import pytest
from models_library.rest_pagination import Page, PageMetaInfoLimitOffset
from pydantic import BaseModel, ValidationError
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


@pytest.mark.parametrize(
    "total, offset",
    [
        pytest.param(0, 0, id="empty collection at offset 0"),
        pytest.param(0, 100, id="empty collection past the end"),
        pytest.param(5, 5, id="offset equal to total"),
        pytest.param(5, 100, id="offset past total"),
    ],
)
def test_offset_past_total_is_valid_empty_page(total: int, offset: int):
    # a request for a page that does not exist yields an empty page carrying the real total
    meta = PageMetaInfoLimitOffset(limit=6, total=total, offset=offset, count=0)
    assert meta.count == 0
    assert meta.total == total
    assert meta.offset == offset


def test_non_empty_page_past_total_is_invalid():
    # a non-empty page beyond the end is a server-side inconsistency, not a client asking
    # too far ahead -- it must keep failing loudly
    with pytest.raises(ValidationError):
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
    with pytest.raises(ValidationError):
        PageMetaInfoLimitOffset(limit=6, total=5, offset=offset, count=count)


def test_data_size_does_not_fit_count():
    example = deepcopy(PAGE_EXAMPLES[0])
    example["_meta"]["count"] = len(example["data"]) - 1
    with pytest.raises(ValidationError):
        Page[str](**example)


def test_empty_data_is_converted_to_list():
    example = deepcopy(PAGE_EXAMPLES[0])
    example["data"] = None
    example["_meta"]["count"] = 0
    model_instance = Page[str](**example)
    assert model_instance
    assert model_instance.data == []
