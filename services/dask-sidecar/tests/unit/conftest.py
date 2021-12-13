# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from pprint import pformat
from typing import Dict, Iterable, List, Optional

import dask
import distributed
import fsspec
import pytest
import requests
import simcore_service_dask_sidecar
from _pytest.monkeypatch import MonkeyPatch
from _pytest.tmpdir import TempPathFactory
from aiohttp.test_utils import loop_context
from faker import Faker
from pytest_localftpserver.servers import ProcessFTPServer
from pytest_mock.plugin import MockerFixture
from yarl import URL

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.environment_configs",
    "pytest_simcore.docker_compose",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "dask-sidecar"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_dask_sidecar"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_dask_sidecar.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture()
def mock_service_envs(
    mock_env_devel_environment: Dict[str, Optional[str]],
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    tmp_path_factory: TempPathFactory,
) -> None:

    # Variables directly define inside Dockerfile
    monkeypatch.setenv("SC_BOOT_MODE", "debug-ptvsd")

    monkeypatch.setenv("SWARM_STACK_NAME", "simcore")
    monkeypatch.setenv("SIDECAR_LOGLEVEL", "DEBUG")
    monkeypatch.setenv(
        "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME", "simcore_computational_shared_data"
    )

    shared_data_folder = tmp_path_factory.mktemp("pytest_comp_shared_data")
    assert shared_data_folder.exists()
    monkeypatch.setenv("SIDECAR_COMP_SERVICES_SHARED_FOLDER", f"{shared_data_folder}")
    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_computational_shared_data_mount_point",
        return_value=shared_data_folder,
    )


@pytest.fixture
def dask_client(mock_service_envs: None) -> Iterable[distributed.Client]:
    print(pformat(dask.config.get("distributed")))
    with distributed.LocalCluster(
        worker_class=distributed.Worker,
        **{
            "resources": {"CPU": 10, "GPU": 10, "MPI": 1},
            "preload": "simcore_service_dask_sidecar.tasks",
        },
    ) as cluster:
        with distributed.Client(cluster) as client:
            yield client


@pytest.fixture(scope="module")
def loop() -> Iterable[asyncio.AbstractEventLoop]:
    with loop_context() as loop:
        yield loop


@pytest.fixture(scope="module")
def http_server(tmp_path_factory: TempPathFactory) -> Iterable[List[URL]]:
    faker = Faker()
    files = ["file_1", "file_2", "file_3"]
    directory_path = tmp_path_factory.mktemp("http_server")
    assert directory_path.exists()
    for fn in files:
        with (directory_path / fn).open("wt") as f:
            f.write(f"This file is named: {fn}\n")
            for s in faker.sentences():
                f.write(f"{s}\n")

    cmd = [sys.executable, "-m", "http.server", "8999"]

    base_url = URL("http://localhost:8999")
    with subprocess.Popen(cmd, cwd=directory_path) as p:
        timeout = 10
        while True:
            try:
                requests.get(f"{base_url}")
                break
            except requests.exceptions.ConnectionError as e:
                time.sleep(0.1)
                timeout -= 0.1
                if timeout < 0:
                    raise RuntimeError("Server did not appear") from e
        # the server must be up
        yield [base_url.with_path(f) for f in files]
        # cleanup now, sometimes it hangs
        p.kill()


@pytest.fixture(scope="module")
def ftp_server(ftpserver: ProcessFTPServer) -> List[URL]:
    faker = Faker()

    files = ["file_1", "file_2", "file_3"]
    ftp_server_base_url = ftpserver.get_login_data(style="url")
    list_of_file_urls = [f"{ftp_server_base_url}/{filename}.txt" for filename in files]
    with fsspec.open_files(list_of_file_urls, "wt") as open_files:
        for index, fp in enumerate(open_files):
            fp.write(f"This is the file contents of '{files[index]}'\n")
            for s in faker.sentences():
                fp.write(f"{s}\n")

    return [URL(f) for f in list_of_file_urls]
