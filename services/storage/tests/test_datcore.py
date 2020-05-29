# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import importlib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import utils
from simcore_service_storage import datcore
from simcore_service_storage.datcore_wrapper import DatcoreWrapper


@pytest.fixture()
def mocked_blackfynn_unavailable(mocker):
    def raise_error(*args, **kargs):
        raise RuntimeError("mocked_blackfynn_unavailable")

    mock = mocker.patch("blackfynn.Blackfynn", raise_error)
    importlib.reload(datcore)
    return mock


async def test_datcore_unavailable(loop, mocked_blackfynn_unavailable):
    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")
    pool = ThreadPoolExecutor(2)

    # must NOT raise but only returns empties
    dcw = DatcoreWrapper(api_token, api_secret, loop, pool)

    assert not dcw.is_communication_enabled

    responsive = await dcw.ping()
    assert not responsive

    res = await dcw.list_files_raw()
    assert res == []


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
