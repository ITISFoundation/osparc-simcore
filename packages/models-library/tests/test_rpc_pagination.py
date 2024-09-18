from typing import Any

import pytest
from models_library.rpc_pagination import PageRpc


@pytest.mark.parametrize(
    "example", PageRpc.model_config["json_schema_extra"]["examples"]
)
def test_create_page_rpc(example: dict[str, Any]):

    expected = PageRpc.model_validate(example)

    assert PageRpc[str].create(
        expected.data,
        total=expected.meta.total,
        limit=expected.meta.limit,
        offset=expected.meta.offset,
    )
