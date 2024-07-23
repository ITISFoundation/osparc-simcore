from typing import Any

import pytest
from models_library.rpc_pagination import PageRpc


@pytest.mark.parametrize("example", PageRpc.Config.schema_extra["examples"])
def test_create_page_rpc(example: dict[str, Any]):

    expected = PageRpc.parse_obj(example)

    assert PageRpc[str].create(
        expected.data,
        total=expected.meta.total,
        limit=expected.meta.limit,
        offset=expected.meta.offset,
    )
