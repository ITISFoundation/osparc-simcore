import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict

from yarl import URL

from ..node_ports import config, data_items_utils, filemanager
from .links import DownloadLink, FileLink, ItemConcreteValue, PortLink

log = logging.getLogger(__name__)


async def get_value_from_link(
    key: str,
    value: PortLink,
    fileToKeyMap: Dict,
    node_port_creator: Callable[[str], Coroutine[Any, Any, Any]],
) -> ItemConcreteValue:
    log.debug("Getting value %s", value)
    # create a node ports for the other node
    other_nodeports = await node_port_creator(value.node_uuid)
    # get the port value through that guy
    log.debug("Received node from DB %s, now returning value", other_nodeports)

    value = await other_nodeports.get(value.output)
    if isinstance(value, Path):
        file_name = value.name
        # move the file to the right final location
        # if a file alias is present use it
        if fileToKeyMap:
            file_name = next(iter(fileToKeyMap))

        file_path = data_items_utils.create_file_path(key, file_name)
        if value == file_path:
            # this can happen in case
            return value
        if file_path.exists():
            file_path.unlink()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(value), str(file_path))
        value = file_path

    return value


async def pull_file_from_store(key: str, fileToKeyMap: Dict, value: FileLink) -> Path:
    log.debug("Getting value from storage %s", value)
    # do not make any assumption about s3_path, it is a str containing stuff that can be anything depending on the store
    local_path = data_items_utils.create_folder_path(key)
    downloaded_file = await filemanager.download_file_from_s3(
        store_id=value.store, s3_object=value.path, local_folder=local_path
    )
    # if a file alias is present use it to rename the file accordingly
    if fileToKeyMap:
        renamed_file = local_path / next(iter(fileToKeyMap))
        if downloaded_file != renamed_file:
            if renamed_file.exists():
                renamed_file.unlink()
            shutil.move(downloaded_file, renamed_file)
            downloaded_file = renamed_file

    return downloaded_file


async def push_file_to_store(file: Path) -> FileLink:
    log.debug("file path %s will be uploaded to s3", file)
    s3_object = data_items_utils.encode_file_id(
        file, project_id=config.PROJECT_ID, node_id=config.NODE_UUID
    )
    store_id = await filemanager.upload_file(
        store_name=config.STORE, s3_object=s3_object, local_file_path=file
    )
    log.debug("file path %s uploaded", file)
    return FileLink(store=store_id, path=s3_object)


async def pull_file_from_download_link(
    key: str, fileToKeyMap: Dict, value: DownloadLink
) -> Path:
    log.debug(
        "Getting value from download link [%s] with label %s",
        value["downloadLink"],
        value.get("label", "undef"),
    )

    download_link = URL(value["downloadLink"])
    local_path = data_items_utils.create_folder_path(key)
    downloaded_file = await filemanager.download_file_from_link(
        download_link,
        local_path,
        file_name=next(iter(fileToKeyMap)) if fileToKeyMap else None,
    )

    return downloaded_file


def is_file_type(port_type: str):
    return port_type.startswith("data:")
