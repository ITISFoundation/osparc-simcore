# pylint:disable=# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from simcore_sdk.node_ports import exceptions
from simcore_sdk.node_ports._data_item import DataItem, DataItemValue


@pytest.mark.parametrize(
    "item_value",
    [
        (26),
        (-746.4748),
        ("some text"),
        (False),
        (True),
        ({"nodeUuid": "asdf-efefsda-efdeda", "output": "out_1"}),
        ({"store": "0", "path": "/simcore/asdlkjf/dsfskr.tmt"}),
        ({"store": 0, "path": "/simcore/asdlkjf/dsfskr.tmt"}),
        ({"store": 1, "path": "/simcore/asdlkjf/dsfskr.tmt"}),
        ({"store": "1", "path": "/simcore/asdlkjf/dsfskr.tmt"}),
        (
            {
                "store": 1,
                "dataset": "N:dataset:f9f5ac51-33ea-4861-8e08-5b4faf655041",
                "path": "N:package:b05739ef-260c-4038-b47d-0240d04b0599",
                "label": "FELIR.job",
            }
        ),
        (
            {
                "downloadLink": "https://github.com/ITISFoundation/osparc-simcore/blob/master/README.md",
                "label": "mylink",
            }
        ),
        (None),
    ],
)
def test_default_item(item_value: DataItemValue):
    with pytest.raises(exceptions.InvalidProtocolError):
        DataItem()
    with pytest.raises(exceptions.InvalidProtocolError):
        DataItem(key="a key")
    with pytest.raises(exceptions.InvalidProtocolError):
        DataItem(value="a value")
    item = DataItem(key="one key", value=item_value)
    assert item.key == "one key"
    assert item.value == item_value
