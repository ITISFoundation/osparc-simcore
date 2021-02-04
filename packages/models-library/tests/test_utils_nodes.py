# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict
from uuid import uuid4

import pytest
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import DownloadLink, PortLink, SimCoreFileLink
from models_library.utils.nodes import compute_node_hash


@pytest.fixture()
def node_id() -> NodeID:
    return uuid4()


ANOTHER_NODE_ID = uuid4()
ANOTHER_NODE_OUTPUT_KEY = "the_output_link"
ANOTHER_NODE_PAYLOAD = {"outputs": {ANOTHER_NODE_OUTPUT_KEY: 36}}


@pytest.mark.parametrize(
    "node_payload, expected_hash",
    [
        (
            {"inputs": None, "outputs": None},
            "23db227371a8c18f25fcb51fef16a74b6ba4136c7988b8da50f17fc5fcff8524",
        ),
        (
            {"inputs": {}, "outputs": {}},
            "3e8b860b6c32dc75b859f3d59c56dfcc0410bacdc623eb3d0d90f36d8720efb0",
        ),
        (
            {
                "inputs": {
                    "input_int": 12,
                    "input_bool": True,
                    "input_string": "string",
                    "input_downloadlink": DownloadLink(
                        downloadLink="http://httpbin.org/image/jpeg"
                    ),
                    "input_simcorelink": SimCoreFileLink(
                        store=0, path="/path/to/some/file"
                    ),
                    "input_portlink": PortLink(
                        nodeUuid=ANOTHER_NODE_ID, output=ANOTHER_NODE_OUTPUT_KEY
                    ),
                    "input_null": None,
                },
                "outputs": {
                    "output_int": 2,
                    "output_bool": False,
                    "output_string": "some string",
                    "output_simcorelink": SimCoreFileLink(
                        store=0, path="/path/to/some/file"
                    ),
                },
            },
            "8acedaf90992acdc0c7d9b6774448206042b424cb9569d06a30519225d1b9e22",
        ),
    ],
)
async def test_compute_node_hash(
    node_id: NodeID, node_payload: Dict[str, Any], expected_hash: str
):
    async def get_node_io_payload_cb(some_node_id: NodeID) -> Dict[str, Any]:
        assert some_node_id in [node_id, ANOTHER_NODE_ID]
        return node_payload if some_node_id == node_id else ANOTHER_NODE_PAYLOAD

    node_hash = await compute_node_hash(node_id, get_node_io_payload_cb)
    assert node_hash == expected_hash, "The computed hash changed"
