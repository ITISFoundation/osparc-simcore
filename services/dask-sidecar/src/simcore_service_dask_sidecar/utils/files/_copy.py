import asyncio
import functools
import logging
import time
from io import IOBase
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

import fsspec  # type: ignore[import-untyped]
from dask_task_models_library.container_tasks.encryption import (
    TransferEncryptionSettings,
)
from pydantic.networks import AnyUrl

from ..aes_gcm import decrypt_stream, encrypt_stream
from ._progress import LogPublishingCB, _format_progress_message, _ThreadSafeProgressLogger

CHUNK_SIZE = 4 * 1024 * 1024

_TransferMode = Literal["encrypt", "decrypt"]


def _file_chunk_streamer(src: IOBase, dst: IOBase):
    data = src.read(CHUNK_SIZE)
    segment_len = dst.write(data)
    return (data, segment_len)


async def _run_plain_copy(
    src_fp: IOBase,
    dst_fp: IOBase,
    *,
    file_size: int | None,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
) -> None:
    data_read = True
    total_data_written = 0
    t = time.perf_counter()
    while data_read:
        (
            data_read,
            data_written,
        ) = await asyncio.to_thread(_file_chunk_streamer, src_fp, dst_fp)
        elapsed_time = time.perf_counter() - t
        total_data_written += data_written or 0
        await log_publishing_cb(
            _format_progress_message(
                text_prefix=text_prefix,
                bytes_transferred=total_data_written,
                file_size=file_size,
                elapsed_time=elapsed_time,
            ),
            logging.DEBUG,
        )


async def _run_crypto_copy(
    src_fp: IOBase,
    dst_fp: IOBase,
    *,
    file_size: int | None,
    encryption: TransferEncryptionSettings,
    encryption_mode: _TransferMode,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
) -> None:
    progress_logger = _ThreadSafeProgressLogger(
        file_size=file_size,
        log_publishing_cb=log_publishing_cb,
        text_prefix=text_prefix,
        main_loop=asyncio.get_running_loop(),
    )
    transfer = encrypt_stream if encryption_mode == "encrypt" else decrypt_stream
    blocking_transfer = functools.partial(
        transfer,
        cast(BinaryIO, src_fp),
        cast(BinaryIO, dst_fp),
        root_key=encryption.root_key.get_secret_value(),
        file_id=encryption.file_id,
        progress_cb=progress_logger,
    )
    await asyncio.to_thread(blocking_transfer)
    # force a final progress log on completion
    await progress_logger.emit_final()


async def _copy_file(
    src_url: AnyUrl | Path,
    dst_url: AnyUrl | Path,
    *,
    log_publishing_cb: LogPublishingCB,
    text_prefix: str,
    src_storage_cfg: dict[str, Any] | None,
    dst_storage_cfg: dict[str, Any] | None,
    encryption: TransferEncryptionSettings | None,
    encryption_mode: _TransferMode | None,
):
    src_storage_kwargs = src_storage_cfg or {}
    dst_storage_kwargs = dst_storage_cfg or {}
    with (
        fsspec.open(f"{src_url}", mode="rb", expand=False, **src_storage_kwargs) as src_fp,
        fsspec.open(f"{dst_url}", mode="wb", expand=False, **dst_storage_kwargs) as dst_fp,
    ):
        assert isinstance(src_fp, IOBase)  # nosec
        assert isinstance(dst_fp, IOBase)  # nosec
        file_size = getattr(src_fp, "size", None)
        if encryption is None:
            await _run_plain_copy(
                src_fp,
                dst_fp,
                file_size=file_size,
                log_publishing_cb=log_publishing_cb,
                text_prefix=text_prefix,
            )
        else:
            if encryption_mode is None:
                msg = "encryption_mode must be provided when encryption settings are configured"
                raise ValueError(msg)
            await _run_crypto_copy(
                src_fp,
                dst_fp,
                file_size=file_size,
                encryption=encryption,
                encryption_mode=encryption_mode,
                log_publishing_cb=log_publishing_cb,
                text_prefix=text_prefix,
            )
