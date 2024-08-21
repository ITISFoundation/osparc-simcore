import asyncio
import concurrent.futures
import time
import timeit
import urllib.parse
from contextlib import contextmanager
from datetime import datetime

import pytest
from simcore_service_webserver.utils import (
    DATETIME_FORMAT,
    compose_support_error_msg,
    compute_sha1_on_small_dataset,
    now_str,
    to_datetime,
)
from yarl import URL


def test_yarl_new_url_generation():
    api_endpoint = URL("http://director:8001/v0")
    service_key = "simcore/services/dynamic/smash"
    service_version = "1.0.3"

    quoted_service_key = urllib.parse.quote(service_key, safe="")

    # Since 1.6.x composition using '/' creates URLs with auto-encoding enabled by default
    assert (
        (str(api_endpoint / "services" / quoted_service_key / service_version))
        == "http://director:8001/v0/services/simcore%252Fservices%252Fdynamic%252Fsmash/1.0.3"
    )

    # Passing encoded=True parameter prevents URL auto-encoding, user is responsible about URL correctness
    url = URL(
        f"http://director:8001/v0/services/{quoted_service_key}/1.0.3", encoded=True
    )

    assert (
        (str(url))
        == "http://director:8001/v0/services/simcore%2Fservices%2Fdynamic%2Fsmash/1.0.3"
    )


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


@pytest.mark.skip(reason="DEV-demo")
async def test_compute_sha1_on_small_dataset(fake_project: dict):
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


def test_compose_support_error_msg():

    msg = compose_support_error_msg(
        "first sentence for Mr.X   \n  Second sentence.",
        error_code="OEC:139641204989600",
        support_email="support@email.com",
    )
    assert (
        msg == "First sentence for Mr.X. Second sentence."
        " For more information please forward this message to support@email.com [OEC:139641204989600]"
    )
