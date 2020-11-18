# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-member

from pathlib import Path

import pytest

from simcore_sdk.node_ports import config, exceptions, filemanager
from simcore_sdk.node_ports import data_items_utils
from simcore_sdk.node_ports._data_item import DataItem
from simcore_sdk.node_ports._item import Item
from simcore_sdk.node_ports._schema_item import SchemaItem

from utils_futures import future_with_result


@pytest.fixture
def node_ports_config():
    config.STORAGE_ENDPOINT = "storage:8080"


def create_item(item_type: str, item_value):
    key = "some key"
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


def test_default_item():
    with pytest.raises(exceptions.InvalidProtocolError):
        Item(None, None)


async def test_item(loop):
    key = "my key"
    label = "my label"
    description = "my description"
    item_type = "boolean"
    item_value = True
    display_order = 2

    item = Item(
        SchemaItem(
            key=key,
            label=label,
            description=description,
            type=item_type,
            displayOrder=display_order,
        ),
        DataItem(key=key, value=item_value),
    )

    assert item.key == key
    assert item.label == label
    assert item.description == description
    assert item.type == item_type
    assert item.value == item_value

    assert item.new_data_cb is None

    assert await item.get() == item_value


@pytest.mark.parametrize(
    "item_type", list(config.TYPE_TO_PYTHON_TYPE_MAP.keys()) + [config.FILE_TYPE_PREFIX]
)
async def test_valid_type_empty_value(item_type: str):
    item = create_item(item_type, None)
    assert await item.get() is None


from pathlib import Path


@pytest.fixture
async def file_manager_mock(monkeypatch):
    async def fake_download_file(*args, **kwargs) -> Path:
        return "/some/file/path"

    monkeypatch.setattr(filemanager, "download_file", fake_download_file)


@pytest.mark.parametrize(
    "item_type, item_value",
    [
        ("integer", None),
        ("integer", -12343),
        ("integer", 1243),
        ("integer", 0),
        ("integer", {"nodeUuid": "some node uuid", "output": "some output"}),
        ("number", None),
        ("number", -12343),
        ("number", 0.000),
        ("number", 3.5434534500),
        ("number", {"nodeUuid": "some node uuid", "output": "some output"}),
        ("boolean", None),
        ("boolean", False),
        ("boolean", 0),
        ("boolean", True),
        ("boolean", {"nodeUuid": "some node uuid", "output": "some output"}),
        ("string", None),
        ("string", "123"),
        ("string", "True"),
        ("string", {"nodeUuid": "some node uuid", "output": "some output"}),
        ("data:*/*", None),
        ("data:*/*", {"store": 0, "path": "/myfile/path"}),
        ("data:*/*", {"store": 0, "path": "/myfile/path"}),
        ("data:*/*", {"nodeUuid": "some node uuid", "output": "some output"}),
    ],
)
async def test_valid_type(item_type: str, item_value):
    item = create_item(item_type, item_value)
    if not data_items_utils.is_file_type(
        item_type
    ) and not data_items_utils.is_value_link(item_value):
        assert await item.get() == item_value


@pytest.mark.parametrize(
    "item_type, item_value",
    [
        ("some wrong type", "some string but not an integer"),
        ("integer", "some string but not an integer"),
        ("integer", 2.34),
        ("integer", {"store": 0, "path": "/myfile/path"}),
        ("number", "some string but not a number"),
        ("number", {"store": 0, "path": "/myfile/path"}),
        ("boolean", "some string but not a boolean"),
        ("boolean", 432),
        ("boolean", 1),
        ("boolean", -1),
        ("boolean", {"store": 0, "path": "/myfile/path"}),
        ("string", 123),
        ("string", True),
        ("string", {"store": 0, "path": "/myfile/path"}),
    ],
)
async def test_invalid_type(item_type, item_value):
    # pylint: disable=W0612
    with pytest.raises(
        exceptions.InvalidItemTypeError, match=rf"Invalid item type, .*[{item_type}]"
    ):
        create_item(item_type, item_value)


@pytest.mark.parametrize(
    "item_type, item_value_to_set, expected_value",
    [
        ("integer", 26, 26),
        ("number", -746.4748, -746.4748),
        #     ("data:*/*", __file__, {"store":"s3-z43", "path":"undefined/undefined/{filename}".format(filename=Path(__file__).name)}),
        ("boolean", False, False),
        ("string", "test-string", "test-string"),
    ],
)
async def test_set_new_value(
    item_type, item_value_to_set, expected_value, mocker
):  # pylint: disable=W0613
    mock_method = mocker.Mock(return_value=future_with_result(""))
    item = create_item(item_type, None)
    item.new_data_cb = mock_method
    assert await item.get() is None
    await item.set(item_value_to_set)
    mock_method.assert_called_with(DataItem(key=item.key, value=expected_value))


@pytest.mark.parametrize(
    "item_type, item_value_to_set",
    [
        ("integer", -746.4748),
        ("number", "a string"),
        ("data:*/*", str(Path(__file__).parent)),
        ("boolean", 123),
        ("string", True),
    ],
)
async def test_set_new_invalid_value(
    item_type, item_value_to_set
):  # pylint: disable=W0613
    item = create_item(item_type, None)
    assert await item.get() is None
    with pytest.raises(exceptions.InvalidItemTypeError) as excinfo:
        await item.set(item_value_to_set)
    assert "Invalid item type" in str(excinfo.value)
