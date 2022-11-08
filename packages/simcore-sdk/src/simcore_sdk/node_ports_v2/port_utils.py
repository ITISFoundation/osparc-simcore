import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

from models_library.api_schemas_storage import FileUploadSchema
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize
from pydantic.tools import parse_obj_as
from settings_library.r_clone import RCloneSettings
from yarl import URL

from ..node_ports_common import data_items_utils, filemanager
from ..node_ports_common.constants import SIMCORE_LOCATION
from ..node_ports_common.filemanager import LogRedirectCB
from ..node_ports_common.storage_client import LinkType
from .links import DownloadLink, FileLink, ItemConcreteValue, ItemValue, PortLink

log = logging.getLogger(__name__)


async def get_value_link_from_port_link(
    value: PortLink,
    node_port_creator: Callable[[str], Coroutine[Any, Any, Any]],
    *,
    file_link_type: LinkType,
) -> Optional[ItemValue]:
    log.debug("Getting value link %s", value)
    # create a node ports for the other node
    other_nodeports = await node_port_creator(value.node_uuid)
    # get the port value through that guy
    log.debug("Received node from DB %s, now returning value link", other_nodeports)

    other_value: Optional[ItemValue] = await other_nodeports.get_value_link(
        value.output, file_link_type=file_link_type
    )
    return other_value


async def get_value_from_link(
    key: str,
    value: PortLink,
    fileToKeyMap: Optional[dict[str, str]],
    node_port_creator: Callable[[str], Coroutine[Any, Any, Any]],
) -> Optional[ItemConcreteValue]:
    log.debug("Getting value %s", value)
    # create a node ports for the other node
    other_nodeports = await node_port_creator(value.node_uuid)
    # get the port value through that guy
    log.debug("Received node from DB %s, now returning value", other_nodeports)

    other_value: Optional[ItemConcreteValue] = await other_nodeports.get(value.output)
    if isinstance(other_value, Path):
        file_name = other_value.name
        # move the file to the right final location
        # if a file alias is present use it
        if fileToKeyMap:
            file_name = next(iter(fileToKeyMap))

        file_path = data_items_utils.create_file_path(key, file_name)
        if other_value == file_path:
            # this is a corner case: in case the output key of the other node has the same name as the input key
            return other_value
        if file_path.exists():
            file_path.unlink()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(f"{other_value}", file_path)
        other_value = file_path

    return other_value


async def get_download_link_from_storage(
    user_id: UserID, value: FileLink, link_type: LinkType
) -> AnyUrl:
    """
    :raises exceptions.NodeportsException
    :raises exceptions.S3InvalidPathError
    :raises exceptions.StorageInvalidCall
    :raises exceptions.StorageServerIssue
    """
    log.debug("getting link to file from storage %s", value)

    link = await filemanager.get_download_link_from_s3(
        user_id=user_id,
        store_id=value.store,
        store_name=None,
        s3_object=value.path,
        link_type=link_type,
    )

    # could raise ValidationError but will never do it since
    assert isinstance(link, URL)  # nosec
    return parse_obj_as(AnyUrl, f"{link}")


async def get_download_link_from_storage_overload(
    user_id: UserID, project_id: str, node_id: str, file_name: str, link_type: LinkType
) -> AnyUrl:
    """Overloads get_download_link_from_storage with arguments that match those in
    get_upload_link_from_storage

    """
    # NOTE: might consider using https://github.com/mrocklin/multipledispatch/ in the future?
    s3_object = data_items_utils.create_simcore_file_id(
        Path(file_name), project_id, node_id
    )
    link = await filemanager.get_download_link_from_s3(
        user_id=user_id,
        store_name=None,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_object,
        link_type=link_type,
    )
    return parse_obj_as(AnyUrl, f"{link}")


async def get_upload_links_from_storage(
    user_id: UserID,
    project_id: str,
    node_id: str,
    file_name: str,
    link_type: LinkType,
    file_size: ByteSize,
) -> FileUploadSchema:
    log.debug("getting link to file from storage for %s", file_name)
    s3_object = data_items_utils.create_simcore_file_id(
        Path(file_name), project_id, node_id
    )
    _, links = await filemanager.get_upload_links_from_s3(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        store_name=None,
        s3_object=s3_object,
        link_type=link_type,
        file_size=file_size,
    )
    return links


async def target_link_exists(
    user_id: UserID, project_id: str, node_id: str, file_name: str
) -> bool:
    log.debug(
        "checking if target of link to file from storage for %s exists", file_name
    )
    s3_object = data_items_utils.create_simcore_file_id(
        Path(file_name), project_id, node_id
    )
    return await filemanager.entry_exists(
        user_id=user_id, store_id=SIMCORE_LOCATION, s3_object=s3_object
    )


async def delete_target_link(
    user_id: UserID, project_id: str, node_id: str, file_name: str
) -> None:
    log.debug("deleting target of link to file from storage for %s", file_name)
    s3_object = data_items_utils.create_simcore_file_id(
        Path(file_name), project_id, node_id
    )
    return await filemanager.delete_file(
        user_id=user_id, store_id=SIMCORE_LOCATION, s3_object=s3_object
    )


async def pull_file_from_store(
    user_id: UserID,
    key: str,
    fileToKeyMap: Optional[dict[str, str]],
    value: FileLink,
    io_log_redirect_cb: Optional[LogRedirectCB],
) -> Path:
    log.debug("pulling file from storage %s", value)
    # do not make any assumption about s3_path, it is a str containing stuff that can be anything depending on the store
    local_path = data_items_utils.create_folder_path(key)
    downloaded_file = await filemanager.download_file_from_s3(
        user_id=user_id,
        store_id=value.store,
        store_name=None,
        s3_object=value.path,
        local_folder=local_path,
        io_log_redirect_cb=io_log_redirect_cb,
    )
    # if a file alias is present use it to rename the file accordingly
    if fileToKeyMap:
        renamed_file = local_path / next(iter(fileToKeyMap))
        if downloaded_file != renamed_file:
            if renamed_file.exists():
                renamed_file.unlink()
            shutil.move(f"{downloaded_file}", renamed_file)
            downloaded_file = renamed_file

    return downloaded_file


async def push_file_to_store(
    file: Path,
    user_id: UserID,
    project_id: str,
    node_id: str,
    io_log_redirect_cb: Optional[LogRedirectCB],
    r_clone_settings: Optional[RCloneSettings] = None,
    file_base_path: Optional[Path] = None,
) -> FileLink:
    log.debug("file path %s will be uploaded to s3", file)
    s3_object = data_items_utils.create_simcore_file_id(
        file, project_id, node_id, file_base_path=file_base_path
    )
    store_id, e_tag = await filemanager.upload_file(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        store_name=None,
        s3_object=s3_object,
        file_to_upload=file,
        r_clone_settings=r_clone_settings,
        io_log_redirect_cb=io_log_redirect_cb,
    )
    log.debug("file path %s uploaded, received ETag %s", file, e_tag)
    return FileLink(store=store_id, path=s3_object, e_tag=e_tag)


async def pull_file_from_download_link(
    key: str,
    fileToKeyMap: Optional[dict[str, str]],
    value: DownloadLink,
    io_log_redirect_cb: Optional[LogRedirectCB],
) -> Path:
    log.debug(
        "Getting value from download link [%s] with label %s",
        value.download_link,
        value.label,
    )

    local_path = data_items_utils.create_folder_path(key)
    downloaded_file = await filemanager.download_file_from_link(
        URL(f"{value.download_link}"), local_path, io_log_redirect_cb=io_log_redirect_cb
    )

    # if a file alias is present use it to rename the file accordingly
    if fileToKeyMap:
        renamed_file = local_path / next(iter(fileToKeyMap))
        if downloaded_file != renamed_file:
            if renamed_file.exists():
                renamed_file.unlink()
            shutil.move(f"{downloaded_file}", renamed_file)
            downloaded_file = renamed_file

    return downloaded_file


def is_file_type(port_type: str) -> bool:
    return port_type.startswith("data:")


async def get_file_link_from_url(
    new_value: AnyUrl,
    user_id: UserID,
    project_id: str,
    node_id: str,
) -> FileLink:
    log.debug("url %s will now be converted to a file link", new_value)
    assert new_value.path  # nosec
    s3_object = data_items_utils.create_simcore_file_id(
        Path(new_value.path), project_id, node_id
    )
    store_id, e_tag = await filemanager.get_file_metadata(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_object,
    )
    log.debug("file meta data for %s found, received ETag %s", new_value, e_tag)
    return FileLink(store=store_id, path=s3_object, e_tag=e_tag)
