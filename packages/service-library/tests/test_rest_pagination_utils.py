from servicelib.rest_pagination_utils import PageResponseLimitOffset


def test_paginate_limit_offset_models():
    examples = PageResponseLimitOffset.Config.schema_extra["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = PageResponseLimitOffset(**example)
        assert model_instance
