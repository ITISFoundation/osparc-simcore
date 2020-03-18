# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import utils
from simcore_service_storage.datcore_wrapper import DatcoreWrapper


async def test_datcore_ping(loop):
    if not utils.has_datcore_tokens():
        return

    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")
    pool = ThreadPoolExecutor(2)
    dcw = DatcoreWrapper(api_token, api_secret, loop, pool)
    responsive = await dcw.ping()
    assert responsive


async def test_datcore_list_files_recursively(loop):
    if not utils.has_datcore_tokens():
        return

    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")
    pool = ThreadPoolExecutor(2)
    dcw = DatcoreWrapper(api_token, api_secret, loop, pool)
    f = await dcw.list_files_recursively()
    assert len(f)


async def test_datcore_list_files_raw(loop):
    if not utils.has_datcore_tokens():
        return

    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")
    pool = ThreadPoolExecutor(2)
    dcw = DatcoreWrapper(api_token, api_secret, loop, pool)
    f = await dcw.list_files_raw()
    assert len(f)


async def test_datcore_nested_download_link(loop):
    if not utils.has_datcore_tokens():
        return

    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")
    pool = ThreadPoolExecutor(2)
    dcw = DatcoreWrapper(api_token, api_secret, loop, pool)
    destination = str(Path("Shared Data/ISAN/UCDavis use case 0D/inputs/"))
    filename = "initial_WTstates.txt"

    f = await dcw.download_link(destination, filename)
    assert f
