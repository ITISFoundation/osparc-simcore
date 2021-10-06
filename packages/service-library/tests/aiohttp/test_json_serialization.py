# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from typing import Any, Dict
from uuid import UUID, uuid4

from servicelib.json_serialization import json_dumps

## HELPERS


def export_uuids_to_str(n: Any):
    if isinstance(n, dict):
        for k, v in n.items():
            n.update({k: export_uuids_to_str(v)})
    elif isinstance(n, list):
        n = [export_uuids_to_str(v) for v in n]
    elif isinstance(n, UUID):
        return str(n)
    return n


# TESTS


def test_serialization_of_uuids(fake_data_dict: Dict[str, Any]):

    uuid_obj = uuid4()
    # NOTE the quotes around expected value
    assert json_dumps(uuid_obj) == f'"{uuid_obj}"'

    obj = {"ids": [uuid4() for _ in range(3)]}
    dump = json_dumps(obj)
    assert json.loads(dump) == export_uuids_to_str(obj)


def test_serialization_of_nested_dicts(fake_data_dict: Dict[str, Any]):

    obj = {"data": fake_data_dict, "ids": [uuid4() for _ in range(3)]}

    dump = json_dumps(obj)
    assert json.loads(dump) == export_uuids_to_str(obj)
