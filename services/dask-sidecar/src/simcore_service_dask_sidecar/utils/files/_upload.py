import asyncio
import functools
import logging
import mimetypes
import zipfile
from pathlib import Path
from typing import Any, Final, cast

import aiofiles
import aiofiles.os
import aiofiles.tempfile
import fsspec  # type: ignore[import-untyped]
import repro_zipfile
from pydantic.networks import AnyUrl
from settings_library.s3 import S3Settings
from yarl import URL

from ...errors import (
    FileTransferEncryptionError,
    HTTPDestinationEncryptionNotSupportedError,
)
from ..aes_gcm import AesGcmStreamError
from ..encryption import TransferEncryptionSettings
from ._copy import _copy_file
from ._progress import LogPublishingCB, _file_progress_cb
from ._s3 import HTTP_FILE_SYSTEM_SCHEMES, S3FsSettingsDict, _s3fs_settings_from_s3_settings

_logger = logging.getLogger(__name__)

_ZIP_MIME_TYPE: Final[str] = "application/zip"

MIMETYPE_APPLICATION_ZIP = "application/zip"


async def _push_file_to_http_link(file_to_upload: Path, dst_url: AnyUrl, log_publishing_cb: LogPublishingCB) -> None:
    # NOTE: special case for http scheme when uploading. this is typically a S3 put presigned link.
    # Therefore, we need to use the http filesystem directly in order to call the put_file function.
    # writing on httpfilesystem is disabled by default.
    fs = fsspec.filesystem(
        "http",
        headers={
            "Content-Length": f"{(await aiofiles.os.stat(file_to_upload)).st_size}",
        },
        asynchronous=True,
    )
    assert dst_url.path  # nosec
    await fs._put_file(  # pylint: disable=protected-access  # noqa: SLF001
        file_to_upload,
        f"{dst_url}",
        method="PUT",
        callback=fsspec.Callback(
            hooks={
                "progress": functools.partial(
                    _file_progress_cb,
                    log_publishing_cb=log_publishing_cb,
                    text_prefix=f"Uploading '{dst_url.path.strip('/')}':",
                    main_loop=asyncio.get_running_loop(),
                )
            }
        ),
    )


async def _push_file_to_remote(
    file_to_upload: Path,
    dst_url: AnyUrl,
    *,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    encryption: TransferEncryptionSettings | None,
) -> None:
    _logger.debug("Uploading %s to %s...", file_to_upload, dst_url)
    assert dst_url.path  # nosec

    storage_kwargs: S3FsSettingsDict | dict[str, Any] = {}
    if s3_settings:
        storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    try:
        await _copy_file(
            file_to_upload,
            dst_url,
            src_storage_cfg=None,
            dst_storage_cfg=cast(dict[str, Any], storage_kwargs),
            log_publishing_cb=log_publishing_cb,
            text_prefix=f"Uploading '{dst_url.path.strip('/')}':",
            encryption=encryption,
            encryption_mode="encrypt" if encryption else None,
        )
    except AesGcmStreamError as exc:
        # translate the low-level crypto failure into a sidecar error so callers do not
        # depend on the crypto primitives. file_id is the one used for key derivation.
        assert encryption is not None  # nosec
        raise FileTransferEncryptionError(
            operation="encrypt",
            file_role="output",
            file_id=encryption.file_id,
            error_message=f"{exc}",
        ) from exc


async def push_file_to_remote(
    src_path: Path,
    dst_url: AnyUrl,
    log_publishing_cb: LogPublishingCB,
    s3_settings: S3Settings | None,
    encryption: TransferEncryptionSettings | None,
) -> None:
    if not await aiofiles.os.path.exists(src_path):
        msg = f"{src_path=} does not exist"
        raise ValueError(msg)
    assert dst_url.path  # nosec
    async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
        file_to_upload = src_path

        dst_mime_type, _ = mimetypes.guess_type(f"{dst_url.path}")
        src_mime_type, _ = mimetypes.guess_type(src_path)

        if dst_mime_type == _ZIP_MIME_TYPE and src_mime_type != _ZIP_MIME_TYPE:
            archive_file_path = Path(tmp_dir) / Path(URL(f"{dst_url}").path).name
            await log_publishing_cb(
                f"Compressing '{src_path.name}' to '{archive_file_path.name}'...",
                logging.INFO,
            )

            with repro_zipfile.ReproducibleZipFile(archive_file_path, mode="w", compression=zipfile.ZIP_STORED) as zfp:
                await asyncio.to_thread(zfp.write, src_path, src_path.name)
            _logger.debug("%s created.", archive_file_path)
            assert archive_file_path.exists()  # nosec
            file_to_upload = archive_file_path
            await log_publishing_cb(
                f"Compression of '{src_path.name}' to '{archive_file_path.name}' complete.",
                logging.INFO,
            )

        await log_publishing_cb(f"Uploading '{file_to_upload.name}' to '{dst_url}'...", logging.INFO)

        if dst_url.scheme in HTTP_FILE_SYSTEM_SCHEMES:
            if encryption is not None:
                raise HTTPDestinationEncryptionNotSupportedError(scheme=dst_url.scheme)
            _logger.debug("destination is a http presigned link")
            await _push_file_to_http_link(file_to_upload, dst_url, log_publishing_cb)
        else:
            await _push_file_to_remote(
                file_to_upload,
                dst_url,
                log_publishing_cb=log_publishing_cb,
                s3_settings=s3_settings,
                encryption=encryption,
            )

    await log_publishing_cb(
        f"Upload of '{src_path.name}' to '{dst_url.path.strip('/')}' complete",
        logging.INFO,
    )
