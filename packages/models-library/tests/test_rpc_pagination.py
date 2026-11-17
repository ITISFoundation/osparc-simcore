import pickle
from typing import Any

import pytest
from models_library.api_schemas_catalog.services import PageRpcServiceSummary
from models_library.rpc.webserver.projects import PageRpcProjectJobRpcGet
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


def test_page_rpc_aliases_are_picklable():
    # RPC payloads pickle these aliases, and `pickle` resolves a class through its `__module__` and
    # `__qualname__`. They are parametrized in a module other than `rpc_pagination`, which pydantic
    # 2.14.0 and 2.14.1 did not register where `pickle` looks for it.
    # SEE https://github.com/pydantic/pydantic/issues/13991
    for alias in (PageRpcProjectJobRpcGet, PageRpcServiceSummary):
        assert pickle.loads(pickle.dumps(alias)) is alias  # noqa: S301
