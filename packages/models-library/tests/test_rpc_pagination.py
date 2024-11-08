from typing import Any

import pytest
from models_library.rpc_pagination import PageRpc
from pytest_simcore.examples.models_library import RPC_PAGE_EXAMPLES


@pytest.mark.parametrize("example", RPC_PAGE_EXAMPLES)
def test_create_page_rpc(example: dict[str, Any]):

    expected = PageRpc.model_validate(example)

    assert PageRpc[str].create(
        expected.data,
        total=expected.meta.total,
        limit=expected.meta.limit,
        offset=expected.meta.offset,
    )
