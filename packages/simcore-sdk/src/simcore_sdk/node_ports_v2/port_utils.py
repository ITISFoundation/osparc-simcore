import logging
import shutil
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from models_library.api_schemas_storage import FileUploadSchema, LinkType
from models_library.basic_types import IDStr, SHA256Str
from models_library.services_types import FileName, ServicePortKey
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.progress_bar import ProgressBarData
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.r_clone import RCloneSettings
from yarl import URL

from ..node_ports_common import data_items_utils, filemanager
from ..node_ports_common.constants import SIMCORE_LOCATION
from ..node_ports_common.exceptions import NodeportsException
from ..node_ports_common.file_io_utils import LogRedirectCB
from ..node_ports_common.filemanager import UploadedFile, UploadedFolder
from .links import DownloadLink, FileLink, ItemConcreteValue, ItemValue, PortLink

log = logging.getLogger(__name__)


async def get_value_link_from_port_link(
    value: PortLink,
    node_port_creator: Callable[[str], Coroutine[Any, Any, Any]],
    *,
    file_link_type: LinkType,
) -> ItemValue | None:
    log.debug("Getting value link %s", value)
    # create a node ports for the other node
    other_nodeports = await node_port_creator(f"{value.node_uuid}")
    # get the port value through that guy
    log.debug("Received node from DB %s, now returning value link", other_nodeports)

    other_value: ItemValue | None = await other_nodeports.get_value_link(
        value.output, file_link_type=file_link_type
    )
    return other_value


async def get_value_from_link(
    key: str,
    value: PortLink,
    file_to_key_map: dict[FileName, ServicePortKey] | None,
    node_port_creator: Callable[[str], Coroutine[Any, Any, Any]],
    *,
    progress_bar: ProgressBarData | None,
) -> ItemConcreteValue | None:
    log.debug("Getting value %s", value)
    # create a node ports for the other node
    other_nodeports = await node_port_creator(f"{value.node_uuid}")
    # get the port value through that guy
    log.debug("Received node from DB %s, now returning value", other_nodeports)

    other_value: ItemConcreteValue | None = await other_nodeports.get(
        value.output, progress_bar
    )
    if isinstance(other_value, Path):
        file_name = other_value.name
        # move the file to the right final location
        # if a file alias is present use it

        if file_to_key_map:
            file_name = next(iter(file_to_key_map))

        file_path = data_items_utils.get_file_path(key, file_name)
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
    url: AnyUrl = TypeAdapter(AnyUrl).validate_python(f"{link}")
    return url


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
    url: AnyUrl = TypeAdapter(AnyUrl).validate_python(f"{link}")
    return url


async def get_upload_links_from_storage(
    user_id: UserID,
    project_id: str,
    node_id: str,
    file_name: str,
    link_type: LinkType,
    file_size: ByteSize,
    sha256_checksum: SHA256Str | None,
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
        is_directory=False,
        sha256_checksum=sha256_checksum,
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
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_object,
        is_directory=False,
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
    file_to_key_map: dict[FileName, ServicePortKey] | None,
    value: FileLink,
    io_log_redirect_cb: LogRedirectCB | None,
    r_clone_settings: RCloneSettings | None,
    progress_bar: ProgressBarData | None,
    aws_s3_cli_settings: AwsS3CliSettings | None,
) -> Path:
    log.debug("pulling file from storage %s", value)
    # do not make any assumption about s3_path, it is a str containing stuff that can be anything depending on the store
    local_path = data_items_utils.get_folder_path(key)
    downloaded_file = await filemanager.download_path_from_s3(
        user_id=user_id,
        store_id=value.store,
        store_name=None,
        s3_object=value.path,
        local_path=local_path,
        io_log_redirect_cb=io_log_redirect_cb,
        r_clone_settings=r_clone_settings,
        progress_bar=progress_bar
        or ProgressBarData(num_steps=1, description=IDStr("pulling file")),
        aws_s3_cli_settings=aws_s3_cli_settings,
    )
    # if a file alias is present use it to rename the file accordingly
    if file_to_key_map:
        renamed_file = local_path / next(iter(file_to_key_map))
        if downloaded_file != renamed_file:
            if renamed_file.exists():
                renamed_file.unlink()
            shutil.move(f"{downloaded_file}", renamed_file)
            downloaded_file = renamed_file

    return downloaded_file


async def push_file_to_store(
    *,
    file: Path,
    user_id: UserID,
    project_id: str,
    node_id: str,
    io_log_redirect_cb: LogRedirectCB | None,
    r_clone_settings: RCloneSettings | None = None,
    file_base_path: Path | None = None,
    progress_bar: ProgressBarData,
    aws_s3_cli_settings: AwsS3CliSettings | None = None,
) -> FileLink:
    """
    :raises exceptions.NodeportsException
    """

    log.debug("file path %s will be uploaded to s3", file)
    s3_object = data_items_utils.create_simcore_file_id(
        file, project_id, node_id, file_base_path=file_base_path
    )
    if not file.is_file():
        msg = f"Expected path={file} should be a file"
        raise NodeportsException(msg)

    upload_result: UploadedFolder | UploadedFile = await filemanager.upload_path(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        store_name=None,
        s3_object=s3_object,
        path_to_upload=file,
        r_clone_settings=r_clone_settings,
        io_log_redirect_cb=io_log_redirect_cb,
        progress_bar=progress_bar,
        aws_s3_cli_settings=aws_s3_cli_settings,
    )
    assert isinstance(upload_result, UploadedFile)  # nosec
    log.debug("file path %s uploaded, received ETag %s", file, upload_result.etag)
    return FileLink(
        store=upload_result.store_id, path=s3_object, eTag=upload_result.etag
    )


async def pull_file_from_download_link(
    key: str,
    file_to_key_map: dict[FileName, ServicePortKey] | None,
    value: DownloadLink,
    io_log_redirect_cb: LogRedirectCB | None,
    progress_bar: ProgressBarData | None,
) -> Path:
    # download 1 file from a link
    log.debug(
        "Getting value from download link [%s] with label %s",
        value.download_link,
        value.label,
    )

    local_path = data_items_utils.get_folder_path(key)
    downloaded_file = await filemanager.download_file_from_link(
        URL(f"{value.download_link}"),
        local_path,
        io_log_redirect_cb=io_log_redirect_cb,
        progress_bar=progress_bar
        or ProgressBarData(num_steps=1, description=IDStr("pulling file")),
    )

    # if a file alias is present use it to rename the file accordingly
    if file_to_key_map:
        renamed_file = local_path / next(iter(file_to_key_map))
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
    file_metadata = await filemanager.get_file_metadata(
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_object,
    )
    log.debug(
        "file meta data for %s found, received ETag %s", new_value, file_metadata.etag
    )
    return FileLink(
        store=file_metadata.location, path=s3_object, eTag=file_metadata.etag
    )
