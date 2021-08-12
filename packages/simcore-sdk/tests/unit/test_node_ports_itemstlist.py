# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member

from typing import Dict, Union

import pytest
from simcore_sdk.node_ports._data_item import DataItem
from simcore_sdk.node_ports._data_items_list import DataItemsList
from simcore_sdk.node_ports._item import Item
from simcore_sdk.node_ports._items_list import ItemsList
from simcore_sdk.node_ports._schema_item import SchemaItem
from simcore_sdk.node_ports._schema_items_list import SchemaItemsList


def create_item(
    key: str, item_type: str, item_value: Union[int, float, bool, str, Dict]
):
    return Item(
        SchemaItem(
            key=key,
            label="a label",
            description="a description",
            type=item_type,
            displayOrder=2,
        ),
        DataItem(key=key, value=item_value),
    )


def create_items_list(
    user_id: int, project_id: str, node_uuid: str, key_item_value_tuples
):
    schemas = SchemaItemsList(
        {
            key: SchemaItem(
                key=key,
                label="a label",
                description="a description",
                type=item_type,
                displayOrder=2,
            )
            for (key, item_type, _) in key_item_value_tuples
        }
    )
    payloads = DataItemsList(
        {
            key: DataItem(key=key, value=item_value)
            for key, _, item_value in key_item_value_tuples
        }
    )
    return ItemsList(user_id, project_id, node_uuid, schemas, payloads)


def test_default_list(user_id: int, project_id: str, node_uuid: str):
    itemslist = ItemsList(
        user_id, project_id, node_uuid, SchemaItemsList(), DataItemsList()
    )

    assert not itemslist
    assert not itemslist.change_notifier
    assert not itemslist.get_node_from_node_uuid_cb


def test_creating_list(
    user_id: int,
    project_id: str,
    node_uuid: str,
):
    itemslist = create_items_list(
        user_id,
        project_id,
        node_uuid,
        [("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)],
    )
    assert len(itemslist) == 3


def test_accessing_by_key(
    user_id: int,
    project_id: str,
    node_uuid: str,
):
    itemslist = create_items_list(
        user_id,
        project_id,
        node_uuid,
        [("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)],
    )
    assert itemslist[0].key == "1"
    assert itemslist["1"].key == "1"
    assert itemslist[1].key == "2"
    assert itemslist["2"].key == "2"
    assert itemslist[2].key == "3"
    assert itemslist["3"].key == "3"


def test_access_by_wrong_key(
    user_id: int,
    project_id: str,
    node_uuid: str,
):
    from simcore_sdk.node_ports import exceptions

    itemslist = create_items_list(
        user_id,
        project_id,
        node_uuid,
        [("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)],
    )
    with pytest.raises(exceptions.UnboundPortError):
        print(itemslist["fdoiht"])


async def test_modifying_items_triggers_cb(
    user_id: int, project_id: str, node_uuid: str, mocker
):  # pylint: disable=C0103
    mock_method = mocker.AsyncMock(return_value="")

    itemslist = create_items_list(
        user_id,
        project_id,
        node_uuid,
        [("1", "integer", 333), ("2", "integer", 333), ("3", "integer", 333)],
    )
    itemslist.change_notifier = mock_method
    await itemslist[0].set(-123)
    mock_method.assert_called_once()
    mock_method.reset_mock()
    await itemslist[0].set(234)
    mock_method.assert_called_once()
