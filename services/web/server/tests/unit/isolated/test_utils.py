import asyncio
import concurrent.futures
import time
import timeit
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from typing import Dict
from urllib.parse import unquote_plus

import pytest
import yarl
from simcore_service_webserver.utils import (
    DATETIME_FORMAT,
    compute_sha1_on_small_dataset,
    now_str,
    snake_to_camel,
    to_datetime,
)
from yarl import URL


def test_time_utils():
    snapshot0 = now_str()

    time.sleep(0.5)
    snapshot1 = now_str()

    now0 = to_datetime(snapshot0)
    now1 = to_datetime(snapshot1)
    assert now0 < now1

    # tests biyective
    now_time = datetime.utcnow()
    snapshot = now_time.strftime(DATETIME_FORMAT)
    assert now_time == datetime.strptime(snapshot, DATETIME_FORMAT)


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("snAke_Fun", "snakeFun"),
        ("", ""),
        # since it assumes snake, notice how these cases get flatten
        ("camelAlready", "camelalready"),
        ("AlmostCamel", "almostcamel"),
        ("_S", "S"),
    ],
)
def test_snake_to_camel(subject, expected):
    assert snake_to_camel(subject) == expected


def test_yarl_url_compose_changed_with_latest_release():
    # TODO: add tests and do this upgrade carefuly. Part of https://github.com/ITISFoundation/osparc-simcore/issues/2008
    #
    # With yarl=1.6.* failed tests/unit/isolated/test_director_api.py::test_director_workflow
    #
    # Actually is more consistent since
    #   services/simcore%2Fservices%2Fdynamic%2Fsmash/1.0.3  is decoposed as  [services, simcore%2Fservices%2Fdynamic%2Fsmash, 1.0.3]
    #
    api_endpoint = URL("http://director:8001/v0")
    service_key = "simcore/services/dynamic/smash"
    service_version = "1.0.3"

    url = (
        api_endpoint
        / "services"
        / urllib.parse.quote(service_key, safe="")
        / service_version
    )

    assert (
        "/",
        "v0",
        "services",
        service_key,
        service_version,
    ) == url.parts, f"In yarl==1.5.1, this fails in {yarl.__version__}"

    assert "simcore/services/dynamic/smash/1.0.3" == unquote_plus(
        "simcore%2Fservices%2Fdynamic%2Fsmash/1.0.3"
    )
    assert (
        urllib.parse.quote(service_key, safe="")
        == "simcore%2Fservices%2Fdynamic%2Fsmash"
    )
    assert (
        urllib.parse.quote_plus(service_key) == "simcore%2Fservices%2Fdynamic%2Fsmash"
    )


@pytest.mark.skip(reason="DEV-demo")
async def test_compute_sha1_on_small_dataset(fake_project: Dict):
    # Based on GitHK review https://github.com/ITISFoundation/osparc-simcore/pull/2556:
    #   From what I know, these having function tend to be a bit CPU intensive, based on the size of the dataset.
    #   Could we maybe have an async version of this function here, run it on an executor?
    #
    # PC: Here we check the overhead of sha when adding a pool executor

    @contextmanager
    def timeit_ctx(what):
        start = timeit.default_timer()
        yield
        stop = timeit.default_timer()
        print(f"Time for {what}:", f"{stop - start} secs")

    # dataset is N copies of a project dataset (typical dataset 'unit' in this module)
    N = 10_000
    data = [
        fake_project,
    ] * N

    print("-" * 100)
    with timeit_ctx("compute_sha1 sync"):
        project_sha2_sync = compute_sha1_on_small_dataset(data)

    with timeit_ctx("compute_sha1 async"):
        loop = asyncio.get_running_loop()
        with concurrent.futures.ProcessPoolExecutor() as pool:
            project_sha2_async = await loop.run_in_executor(
                pool, compute_sha1_on_small_dataset, data
            )

    assert project_sha2_sync == project_sha2_async

    # N=1
    #   Time for compute_sha1_sync: 3.153807483613491e-05 secs
    #   Time for compute_sha1_async: 0.03046882478520274 secs

    # N=100
    # Time for compute_sha1 sync: 0.0005367340054363012 secs
    # Time for compute_sha1 async: 0.029975621961057186 secs

    # N=1000
    # Time for compute_sha1 sync: 0.005468853982165456 secs
    # Time for compute_sha1 async: 0.04451707797124982 secs

    # N=10000
    # Time for compute_sha1 sync: 0.05151305114850402 secs
    # Time for compute_sha1 async: 0.09799357503652573 secs

    # For larger datasets, async solution definitvely scales better
    # but for smaller ones, the overhead is considerable
