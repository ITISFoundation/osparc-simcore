# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any
from uuid import uuid4

import pytest
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import (
    DownloadLink,
    PortLink,
    SimCoreFileLink,
    SimcoreS3FileID,
)
from models_library.utils.nodes import compute_node_hash

ANOTHER_NODE_ID = uuid4()
ANOTHER_NODE_OUTPUT_KEY = "the_output_link"
ANOTHER_NODE_PAYLOAD = {"outputs": {ANOTHER_NODE_OUTPUT_KEY: 36}}


@pytest.mark.parametrize(
    "node_payload, expected_hash",
    [
        (
            {"inputs": None, "outputs": None},
            "6c4d5b04b166697ef6eddc63d6c1ee4092dccf8af91a0f7efc55bc423984ea5a",
        ),
        (
            {"inputs": {}, "outputs": {}},
            "d98878dbcffbb908ee6d96d3ca87cc0c083f75683488c50ce9c945bef0588047",
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
                        store=0,
                        path=SimcoreS3FileID(
                            "api/6cb6d306-2b05-49ed-8d6a-5deca53d184a/file.ext"
                        ),
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
                        store=0,
                        path=SimcoreS3FileID(
                            "80af5a16-b066-496f-bfbc-bde359630381/6cb6d306-2b05-49ed-8d6a-5deca53d184a/file.ext"
                        ),
                    ),
                },
            },
            "5ff07b563f9b3d3fad6bfa596bbd6155d3dda02681342f86e5db2d7bcdccd76d",
        ),
    ],
)
async def test_compute_node_hash(
    node_id: NodeID, node_payload: dict[str, Any], expected_hash: str
):
    async def get_node_io_payload_cb(some_node_id: NodeID) -> dict[str, Any]:
        assert some_node_id in [node_id, ANOTHER_NODE_ID]
        return node_payload if some_node_id == node_id else ANOTHER_NODE_PAYLOAD

    node_hash = await compute_node_hash(node_id, get_node_io_payload_cb)
    assert node_hash == expected_hash, "The computed hash changed"
