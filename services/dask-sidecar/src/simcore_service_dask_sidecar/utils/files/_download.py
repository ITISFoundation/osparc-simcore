import asyncio
import logging
import mimetypes
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Final, cast

import aiofiles.tempfile
import repro_zipfile
from pydantic.networks import AnyUrl
from settings_library.s3 import S3Settings
from yarl import URL

from ...errors import FileTransferEncryptionError
from ..aes_gcm import AesGcmStreamError
from ..encryption import TransferEncryptionSettings
from ._copy import _copy_file
from ._progress import LogPublishingCB
from ._s3 import S3_FILE_SYSTEM_SCHEMES, S3FsSettingsDict, _s3fs_settings_from_s3_settings

_logger = logging.getLogger(__name__)

_ZIP_MIME_TYPE: Final[str] = "application/zip"


def check_need_unzipping(
    src_url: AnyUrl,
    target_mime_type: str | None,
    dst_path: Path,
) -> bool:
    """
    Checks if the source URL points to a zip file and if the target mime type is not zip.
    If so, extraction is needed.
    """
    assert src_url.path  # nosec
    src_mime_type, _ = mimetypes.guess_type(src_url.path)
    dst_mime_type = target_mime_type
    if not dst_mime_type:
        dst_mime_type, _ = mimetypes.guess_type(dst_path)
    return (src_mime_type == _ZIP_MIME_TYPE) and (dst_mime_type != _ZIP_MIME_TYPE)


async def pull_file_from_remote(
    src_url: AnyUrl,
    target_mime_type: str | None,
    dst_path: Path,
    *,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    encryption: TransferEncryptionSettings | None,
) -> None:
    assert src_url.path  # nosec
    src_location_str = f"{src_url.path.strip('/')} on {src_url.host}:{src_url.port}"
    await log_publishing_cb(
        f"Downloading '{src_location_str}' into local file '{dst_path}'...",
        logging.INFO,
    )
    if not dst_path.parent.exists():
        msg = f"{dst_path.parent=} does not exist. It must be created by the caller"
        raise ValueError(msg)

    storage_kwargs: S3FsSettingsDict | dict[str, Any] = {}
    if s3_settings and src_url.scheme in S3_FILE_SYSTEM_SCHEMES:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    need_unzipping = check_need_unzipping(src_url, target_mime_type, dst_path)
    async with AsyncExitStack() as exit_stack:
        if need_unzipping:
            # we need to extract the file, so we create a temporary directory
            # where the file will be downloaded and extracted
            tmp_dir = await exit_stack.enter_async_context(aiofiles.tempfile.TemporaryDirectory())
            # NOTE: the URL path is percent-encoded
            download_dst_path = Path(tmp_dir) / Path(URL(f"{src_url}").path).name
        else:
            # no extraction needed, so we can use the provided dst_path directly
            download_dst_path = dst_path

        try:
            await _copy_file(
                src_url,
                download_dst_path,
                src_storage_cfg=cast(dict[str, Any], storage_kwargs),
                dst_storage_cfg=None,
                log_publishing_cb=log_publishing_cb,
                text_prefix=f"Downloading '{src_location_str}':",
                encryption=encryption,
                encryption_mode="decrypt" if encryption else None,
            )
        except AesGcmStreamError as exc:
            # translate the low-level crypto failure into a sidecar error so callers do not
            # depend on the crypto primitives. file_id is the one used for key derivation.
            assert encryption is not None  # nosec
            raise FileTransferEncryptionError(
                operation="decrypt",
                file_role="input",
                file_id=encryption.file_id,
                error_message=f"{exc}",
            ) from exc

        await log_publishing_cb(
            f"Download of '{src_location_str}' into local file '{download_dst_path}' complete.",
            logging.INFO,
        )

        if need_unzipping:
            await log_publishing_cb(f"Uncompressing '{download_dst_path.name}'...", logging.INFO)
            _logger.debug("%s is a zip file and will be now uncompressed", download_dst_path)
            with repro_zipfile.ReproducibleZipFile(download_dst_path, "r") as zip_obj:
                await asyncio.to_thread(zip_obj.extractall, dst_path.parents[0])
            # finally remove the zip archive
            await log_publishing_cb(f"Uncompressing '{download_dst_path.name}' complete.", logging.INFO)
