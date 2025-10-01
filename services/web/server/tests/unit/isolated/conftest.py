# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import json
import logging
import os
import random
from pathlib import Path

import pytest
from faker import Faker
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.monkeypatch_envs import (
    setenvs_from_dict,
    setenvs_from_envfile,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.application_settings_utils import AppConfigDict


@pytest.fixture
def dir_with_random_content(tmpdir, faker: Faker) -> Path:
    def make_files_in_dir(dir_path: Path, file_count: int) -> None:
        for _ in range(file_count):
            (dir_path / f"{faker.file_name(extension='bin')}").write_bytes(
                os.urandom(random.randint(1, 10))  # noqa: S311
            )

    def ensure_dir(path_to_ensure: Path) -> Path:
        path_to_ensure.mkdir(parents=True, exist_ok=True)
        return path_to_ensure

    def make_subdirectory_with_content(subdir_name: Path, max_file_count: int) -> None:
        subdir_name = ensure_dir(subdir_name)
        make_files_in_dir(
            dir_path=subdir_name,
            file_count=random.randint(1, max_file_count),  # noqa: S311
        )

    def make_subdirectories_with_content(
        subdir_name: Path, max_subdirectories_count: int, max_file_count: int
    ) -> None:
        subdirectories_count = random.randint(1, max_subdirectories_count)  # noqa: S311
        for _ in range(subdirectories_count):
            make_subdirectory_with_content(
                subdir_name=subdir_name / f"{faker.word()}",
                max_file_count=max_file_count,
            )

    # -----------------------

    temp_dir_path = Path(tmpdir)
    data_container = ensure_dir(temp_dir_path / "study_data")

    make_subdirectories_with_content(
        subdir_name=data_container, max_subdirectories_count=5, max_file_count=5
    )
    make_files_in_dir(dir_path=data_container, file_count=5)

    # creates a good amount of files
    for _ in range(4):
        for subdirectory_path in (
            path for path in data_container.glob("*") if path.is_dir()
        ):
            make_subdirectories_with_content(
                subdir_name=subdirectory_path,
                max_subdirectories_count=3,
                max_file_count=3,
            )

    return temp_dir_path


@pytest.fixture
def app_config_for_production_legacy(test_data_dir: Path) -> AppConfigDict:
    app_config = json.loads(
        (test_data_dir / "server_docker_prod_app_config-unit.json").read_text()
    )

    print("app config (legacy) used in production:\n", json.dumps(app_config, indent=1))
    return app_config


@pytest.fixture
def mock_env_deployer_pipeline(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    # git log --tags --simplify-by-decoration --pretty="format:%ci %d"
    #  2023-02-08 18:34:56 +0000  (tag: v1.47.0, tag: staging_ResistanceIsFutile12)
    #  2023-02-06 18:40:07 +0100  (tag: v1.46.0, tag: staging_ResistanceIsFutile11)
    #  2023-02-03 17:27:24 +0100  (tag: staging_ResistanceIsFutile10)
    # WARNING: this format works 2023-02-10T18:03:35.957601
    return setenvs_from_dict(
        monkeypatch,
        envs={
            "SIMCORE_VCS_RELEASE_TAG": "staging_ResistanceIsFutile12",
        },
    )


@pytest.fixture
def mock_env_devel_environment(
    env_devel_dict: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    # Overrides to ensure dev-features are enabled testings
    return setenvs_from_dict(
        monkeypatch,
        envs={
            **env_devel_dict,
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "null",
            "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "null",
        },
    )


@pytest.fixture
def mock_env_makefile(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    """envvars produced @Makefile (export)"""
    # TODO: add Makefile recipe 'make dump-envs' to produce the file we load here
    return setenvs_from_dict(
        monkeypatch,
        {
            "API_SERVER_API_VERSION": "0.3.0",
            "BUILD_DATE": "2022-01-14T21:28:15Z",
            "CATALOG_API_VERSION": "0.3.2",
            "CLIENT_WEB_OUTPUT": "/home/crespo/devp/osparc-simcore/services/static-webserver/client/source-output",
            "DATCORE_ADAPTER_API_VERSION": "0.1.0-alpha",
            "DIRECTOR_API_VERSION": "0.1.0",
            "DIRECTOR_V2_API_VERSION": "2.0.0",
            "DOCKER_IMAGE_TAG": "production",
            "DOCKER_REGISTRY": "local",
            "S3_ENDPOINT": "http://127.0.0.1:9001",
            "STORAGE_API_VERSION": "0.2.1",
            "SWARM_HOSTS": "",
            "SWARM_STACK_NAME": "master-simcore",
            "SWARM_STACK_NAME_NO_HYPHEN": "master_simcore",
            "VCS_REF_CLIENT": "99b8022d2",
            "VCS_STATUS_CLIENT": "'modified/untracked'",
            "VCS_URL": "git@github.com:pcrespov/osparc-simcore.git",
            "WEBSERVER_API_VERSION": "0.7.0",
        },
    )


@pytest.fixture
def mock_env_dockerfile_build(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    #
    # docker run -it --hostname "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}" local/webserver:production printenv
    #
    return setenvs_from_envfile(
        monkeypatch,
        """\
        GPG_KEY=123456789123456789
        HOME=/home/scu
        HOSTNAME=osparc-master-55-master-simcore_master_webserver-1
        IS_CONTAINER_CONTEXT=Yes
        LANG=C.UTF-8
        PATH=/home/scu/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        PWD=/home/scu
        PYTHON_GET_PIP_SHA256=6123659241292b2147b58922b9ffe11dda66b39d52d8a6f3aa310bc1d60ea6f7
        PYTHON_GET_PIP_URL=https://github.com/pypa/get-pip/raw/a1675ab6c2bd898ed82b1f58c486097f763c74a9/public/get-pip.py
        PYTHON_PIP_VERSION=21.1.3
        PYTHON_VERSION=3.11.9
        PYTHONDONTWRITEBYTECODE=1
        PYTHONOPTIMIZE=TRUE
        SC_BOOT_MODE=production
        SC_BUILD_DATE=2022-01-09T12:26:29Z
        SC_BUILD_TARGET=production
        SC_HEALTHCHECK_INTERVAL=30
        SC_HEALTHCHECK_RETRY=3
        SC_USER_ID=8004
        SC_USER_NAME=scu
        SC_VCS_REF=dd536f998
        SC_VCS_URL=git@github.com:ITISFoundation/osparc-simcore.git
        TERM=xterm
        VIRTUAL_ENV=/home/scu/.venv
    """,
    )


@pytest.fixture
def mock_webserver_service_environment(
    monkeypatch: pytest.MonkeyPatch,
    mock_env_makefile: EnvVarsDict,
    mock_env_dockerfile_build: EnvVarsDict,
    mock_env_deployer_pipeline: EnvVarsDict,
    docker_compose_service_environment_dict: EnvVarsDict,
    service_name: str,
) -> EnvVarsDict:
    """
    Mocks environment produce in the docker compose config with a .env (.env-devel)
    and launched with a makefile
    """
    logging.getLogger().info("Composing %s service environment ... ", service_name)

    # @docker compose config (overrides)
    # TODO: get from docker compose config
    # r'- ([A-Z2_]+)=\$\{\1:-([\w-]+)\}'

    # - .env-devel + docker-compose service environs
    #     hostname: "{{.Node.Hostname}}-{{.Service.Name}}-{{.Task.Slot}}"

    #     environment:
    #         - CATALOG_HOST=${CATALOG_HOST:-catalog}
    #         - CATALOG_PORT=${CATALOG_PORT:-8000}
    #         - DIAGNOSTICS_MAX_AVG_LATENCY=10
    #         - DIAGNOSTICS_MAX_TASK_DELAY=30
    #         - DIRECTOR_PORT=${DIRECTOR_PORT:-8080}
    #         - DIRECTOR_V2_HOST=${DIRECTOR_V2_HOST:-director-v2}
    #         - DIRECTOR_V2_PORT=${DIRECTOR_V2_PORT:-8000}
    #         - STORAGE_HOST=${STORAGE_HOST:-storage}
    #         - STORAGE_PORT=${STORAGE_PORT:-8080}
    #         - SWARM_STACK_NAME=${SWARM_STACK_NAME:-simcore}
    #         - WEBSERVER_LOGLEVEL=${LOG_LEVEL:-WARNING}
    #     env_file:
    #         - ../.env
    mock_envs_docker_compose_environment = setenvs_from_dict(
        monkeypatch,
        {
            # Emulates MYVAR=${MYVAR:-default}
            "CATALOG_HOST": os.environ.get("CATALOG_HOST", "catalog"),
            "CATALOG_PORT": os.environ.get("CATALOG_PORT", "8000"),
            "DIAGNOSTICS_MAX_AVG_LATENCY": "30",
            "DIRECTOR_PORT": os.environ.get("DIRECTOR_PORT", "8080"),
            "DIRECTOR_V2_HOST": os.environ.get("DIRECTOR_V2_HOST", "director-v2"),
            "DIRECTOR_V2_PORT": os.environ.get("DIRECTOR_V2_PORT", "8000"),
            "STORAGE_HOST": os.environ.get("STORAGE_HOST", "storage"),
            "STORAGE_PORT": os.environ.get("STORAGE_PORT", "8080"),
            "SWARM_STACK_NAME": os.environ.get("SWARM_STACK_NAME", "simcore"),
            "WEBSERVER_LOGLEVEL": os.environ.get("LOG_LEVEL", "WARNING"),
            "SESSION_COOKIE_MAX_AGE": str(7 * 24 * 60 * 60),
            **docker_compose_service_environment_dict,
        },
    )

    envs = (
        mock_env_makefile
        | mock_env_dockerfile_build
        | mock_env_deployer_pipeline
        | mock_envs_docker_compose_environment
    )

    logging.getLogger().info(
        "%s service environment:\n%s", service_name, json.dumps(envs, indent=1)
    )
    return envs


@pytest.fixture
def mocked_login_required(mocker: MockerFixture):

    user_id = 1

    # patches @login_required decorator
    # avoids having to start database etc...
    mocker.patch(
        "simcore_service_webserver.login_auth.decorators.security_web.check_user_authorized",
        spec=True,
        return_value=user_id,
    )

    mocker.patch(
        "simcore_service_webserver.login_auth.decorators.security_web.check_user_permission",
        spec=True,
        return_value=None,
    )

    mocker.patch(
        "simcore_service_webserver.login_auth.decorators.products_web.get_product_name",
        spec=True,
        return_value="osparc",
    )


@pytest.fixture
def mocked_db_setup_in_setup_security(mocker: MockerFixture) -> MockType:
    """Mocking avoids setting up a full db"""
    import simcore_service_webserver.security.plugin

    return mocker.patch.object(
        simcore_service_webserver.security.plugin,
        "setup_db",
        autospec=True,
        return_value=True,
    )
