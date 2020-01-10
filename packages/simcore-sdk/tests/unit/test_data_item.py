# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from simcore_sdk.node_ports import exceptions
from simcore_sdk.node_ports._data_item import DataItem


@pytest.mark.parametrize("item_value", [
    (26),
    (-746.4748),
    ("some text"),
    (False),
    (True),
    ({"nodeUuid":"asdf-efefsda-efdeda", "output":"out_1"}),
    ({"store":"z43", "path":"/simcore/asdlkjf/dsfskr.tmt"}),
    (None)
])
def test_default_item(item_value):
    with pytest.raises(exceptions.InvalidProtocolError):
        DataItem()
    with pytest.raises(exceptions.InvalidProtocolError):
        DataItem(key="a key")
    with pytest.raises(exceptions.InvalidProtocolError):
        DataItem(value="a value")
    item = DataItem(key="one key", value=item_value)
    assert item.key == "one key"
    assert item.value == item_value
