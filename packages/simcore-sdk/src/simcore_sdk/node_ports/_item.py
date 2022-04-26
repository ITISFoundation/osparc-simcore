import logging
import shutil
from pathlib import Path
from typing import Callable, Dict, Optional, Union

from yarl import URL

from ..node_ports_common import config, data_items_utils, exceptions, filemanager
from ._data_item import DataItem, DataItemValue
from ._schema_item import SchemaItem

log = logging.getLogger(__name__)


ItemConcreteValue = Union[int, float, bool, str, Path, Dict[str, str]]
NodeLink = Dict[str, str]
StoreLink = Dict[str, str]
DownloadLink = Dict[str, str]


def _check_type(item_type: str, value: DataItemValue):
    if (
        item_type not in config.TYPE_TO_PYTHON_TYPE_MAP
        and not data_items_utils.is_file_type(item_type)
    ):
        raise exceptions.InvalidItemTypeError(item_type, f"{value}")

    if not value:
        return
    if data_items_utils.is_value_link(value):
        return

    if isinstance(value, (int, float)) and item_type == "number":
        return

    possible_types = [
        key
        for key, key_type in config.TYPE_TO_PYTHON_TYPE_MAP.items()
        if isinstance(value, key_type["type"])
    ]
    if item_type in possible_types:
        return
    if data_items_utils.is_file_type(item_type):
        if data_items_utils.is_value_on_store(
            value
        ) or data_items_utils.is_value_a_download_link(value):
            return
    raise exceptions.InvalidItemTypeError(item_type, f"{value}")


class Item:
    """An item contains data (DataItem) and an schema (SchemaItem)

    raises exceptions.InvalidProtocolError
    raises AttributeError
    raises exceptions.InvalidProtocolError
    raises exceptions.InvalidItemTypeError
    raises exceptions.NodeportsException
    """

    def __init__(
        self,
        user_id: int,
        project_id: str,
        node_uuid: str,
        schema: SchemaItem,
        data: DataItem,
    ):
        if not schema:
            raise exceptions.InvalidProtocolError(None, msg="empty schema or payload")
        self._schema = schema
        self._data = data
        self._user_id = user_id
        self._project_id = project_id
        self._node_uuid = node_uuid
        self.new_data_cb: Optional[Callable] = None
        self.get_node_from_uuid_cb: Optional[Callable] = None

        _check_type(self.type, self.value)

    def __getattr__(self, name: str):

        # schema attributes first
        if hasattr(self._schema, name):
            return getattr(self._schema, name)

        # data attributes then
        if hasattr(self._data, name):
            return getattr(self._data, name)

        if "value" in name and not self._data:
            return getattr(self._schema, "defaultValue", None)

        raise AttributeError

    async def get(self) -> Optional[ItemConcreteValue]:
        """gets data converted to the underlying type

        raises exceptions.InvalidProtocolError: if the underlying type is unknown
        return the converted value or None if no value is defined
        """
        log.debug("Getting item %s", self.key)
        if (
            self.type not in config.TYPE_TO_PYTHON_TYPE_MAP
            and not data_items_utils.is_file_type(self.type)
        ):
            raise exceptions.InvalidProtocolError(self.type)
        if self.value is None:
            log.debug("Got empty [%s] item", self.type)
            return None
        log.debug("Getting [%s] item with value %s", self.type, self.value)

        if data_items_utils.is_value_link(self.value):
            # follow the link
            value = await self.__get_value_from_link(self.value)

            if value and data_items_utils.is_file_type(self.type):
                # move the file to the right location
                file_name = Path(value).name  # type: ignore

                # if a file alias is present use it
                if self._schema.fileToKeyMap:
                    file_name = next(iter(self._schema.fileToKeyMap))

                file_path = data_items_utils.create_file_path(self.key, file_name)
                if value == file_path:
                    # this can happen in case
                    return value
                if file_path.exists():
                    file_path.unlink()
                file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(value), str(file_path))
                value = file_path
            return value

        if data_items_utils.is_value_on_store(self.value):
            return await self.__get_value_from_store(self._user_id, self.value)

        if data_items_utils.is_value_a_download_link(self.value):
            return await self._get_value_from_download_link(self.value)
        # the value is not a link, let's directly convert it to the right type
        return config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["type"](
            config.TYPE_TO_PYTHON_TYPE_MAP[self.type]["converter"](self.value)
        )

    async def set(self, value: ItemConcreteValue):
        """sets the data to the underlying port

        :param value: must be convertible to a string, or an exception will be thrown.
        :type value:
        raises exceptions.InvalidItemTypeError
        raises exceptions.InvalidItemTypeError
        """

        log.info("Setting data item with value %s", value)
        # try to guess the type and check the type set fits this (there can be more than one possibility, e.g. string)
        possible_types = [
            key
            for key, key_type in config.TYPE_TO_PYTHON_TYPE_MAP.items()
            if isinstance(value, key_type["type"])
        ]
        log.debug("possible types are for value %s are %s", value, possible_types)
        if not self.type in possible_types:
            if not data_items_utils.is_file_type(self.type) or not isinstance(
                value, (Path, str)
            ):
                raise exceptions.InvalidItemTypeError(self.type, f"{value}")

        # upload to S3 if file
        if data_items_utils.is_file_type(self.type):
            file_path = Path(value)  # type: ignore
            if not file_path.exists() or not file_path.is_file():
                raise exceptions.InvalidItemTypeError(self.type, f"{value}")
            log.debug("file path %s will be uploaded to s3", value)
            s3_object = data_items_utils.encode_file_id(
                file_path, project_id=self._project_id, node_id=self._node_uuid
            )
            store_id, _ = await filemanager.upload_file(
                user_id=self._user_id,
                store_id=None,
                store_name=config.STORE,
                s3_object=s3_object,
                local_file_path=file_path,
            )
            log.debug("file path %s uploaded", value)
            value = data_items_utils.encode_store(store_id, s3_object)

        # update the DB
        # let's create a new data if necessary
        new_data = DataItem(key=self.key, value=value)
        if self.new_data_cb:
            log.debug("calling new data callback to update database")
            await self.new_data_cb(new_data)  # pylint: disable=not-callable
            log.debug("database updated")

    async def __get_value_from_link(
        self, value: NodeLink
    ) -> Union[int, float, bool, str, Path]:  # pylint: disable=R1710
        log.debug("Getting value %s", value)
        node_uuid, port_key = data_items_utils.decode_link(value)
        if not self.get_node_from_uuid_cb:
            raise exceptions.NodeportsException(
                "callback to get other node information is not set"
            )
        # create a node ports for the other node
        # pylint: disable=not-callable
        other_nodeports = await self.get_node_from_uuid_cb(node_uuid)
        # get the port value through that guy
        log.debug("Received node from DB %s, now returning value", other_nodeports)
        return await other_nodeports.get(port_key)

    async def __get_value_from_store(self, user_id: int, value: StoreLink) -> Path:
        log.debug("Getting value from storage %s", value)
        store_id, s3_path = data_items_utils.decode_store(value)
        # do not make any assumption about s3_path, it is a str containing stuff that can be anything depending on the store
        local_path = data_items_utils.create_folder_path(self.key)
        downloaded_file = await filemanager.download_file_from_s3(
            user_id=user_id,
            store_id=store_id,
            store_name=None,
            s3_object=s3_path,
            local_folder=local_path,
        )
        # if a file alias is present use it to rename the file accordingly
        if self._schema.fileToKeyMap:
            renamed_file = local_path / next(iter(self._schema.fileToKeyMap))
            if downloaded_file != renamed_file:
                if renamed_file.exists():
                    renamed_file.unlink()
                shutil.move(f"{downloaded_file}", renamed_file)
                downloaded_file = renamed_file

        return downloaded_file

    async def _get_value_from_download_link(self, value: DownloadLink) -> Path:
        log.debug(
            "Getting value from download link [%s] with label %s",
            value["downloadLink"],
            value.get("label", "undef"),
        )

        download_link = URL(value["downloadLink"])
        local_path = data_items_utils.create_folder_path(self.key)
        downloaded_file = await filemanager.download_file_from_link(
            download_link,
            local_path,
            file_name=next(iter(self._schema.fileToKeyMap))
            if self._schema.fileToKeyMap
            else None,
        )

        return downloaded_file
