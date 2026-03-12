from aiohttp.test_utils import make_mocked_request
from servicelib.aiohttp.tracing import _collect_custom_request_attributes


def test_collect_custom_request_attributes_from_match_info():
    request = make_mocked_request(
        method="GET",
        path="/v0/projects/p123/nodes/n456",
        match_info={"project_id": "p123", "node_id": "n456"},
    )

    assert _collect_custom_request_attributes(request) == {
        "project_id": "p123",
        "node_id": "n456",
    }
