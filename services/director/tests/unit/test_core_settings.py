# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from pytest_simcore.helpers.monkeypatch_envs import (
    setenvs_from_dict,
    setenvs_from_envfile,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director.core.settings import ApplicationSettings


def test_valid_web_application_settings(app_environment: EnvVarsDict):
    """
    We validate actual envfiles (e.g. repo.config files) by passing them via the CLI

    $ ln -s /path/to/osparc-config/deployments/mydeploy.com/repo.config .secrets
    $ pytest --external-envfile=.secrets --pdb tests/unit/test_core_settings.py

    """
    settings = ApplicationSettings()  # type: ignore
    assert settings

    assert settings == ApplicationSettings.create_from_envs()

    assert (
        str(
            app_environment.get(
                "DIRECTOR_DEFAULT_MAX_MEMORY",
                ApplicationSettings.model_fields["DIRECTOR_DEFAULT_MAX_MEMORY"].default,
            )
        )
        == f"{settings.DIRECTOR_DEFAULT_MAX_MEMORY}"
    )


def test_docker_container_env_sample(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DIRECTOR_DEFAULT_MAX_MEMORY", raising=False)

    setenvs_from_envfile(
        monkeypatch,
        """
        DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS={}
        DIRECTOR_REGISTRY_CACHING=True
        DIRECTOR_REGISTRY_CACHING_TTL=00:15:00
        DIRECTOR_SELF_SIGNED_SSL_FILENAME=
        DIRECTOR_SELF_SIGNED_SSL_SECRET_ID=
        DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME=
        DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS=node.labels.io.simcore.autoscaled-node!=true
        EXTRA_HOSTS_SUFFIX=undefined
        GPG_KEY=0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D
        HOME=/root
        HOSTNAME=osparc-master-01-2
        LANG=C.UTF-8
        LC_ALL=C.UTF-8
        LOGLEVEL=WARNING
        MONITORING_ENABLED=True
        PATH=/home/scu/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        POSTGRES_DB=simcoredb
        POSTGRES_ENDPOINT=master_postgres:5432
        POSTGRES_HOST=master_postgres
        POSTGRES_PASSWORD=z43
        POSTGRES_PORT=5432
        POSTGRES_USER=scu
        PUBLISHED_HOST_NAME=osparc-master.speag.com
        PWD=/home/scu
        PYTHONDONTWRITEBYTECODE=1
        PYTHONOPTIMIZE=TRUE
        PYTHON_GET_PIP_SHA256=adsfasdf
        PYTHON_GET_PIP_URL=https://github.com/pypa/get-pip/raw/eff16c878c7fd6b688b9b4c4267695cf1a0bf01b/get-pip.py
        PYTHON_PIP_VERSION=20.1.1
        PYTHON_VERSION=3.6.10
        REGISTRY_AUTH=True
        REGISTRY_PATH=
        REGISTRY_PW=adsfasdf
        REGISTRY_SSL=True
        REGISTRY_URL=registry.osparc-master.speag.com
        REGISTRY_USER=admin
        REGISTRY_VERSION=v2
        S3_ACCESS_KEY=adsfasdf
        S3_BUCKET_NAME=master-simcore
        S3_ENDPOINT=https://ceph-prod-rgw.speag.com
        S3_REGION=us-east-1
        S3_SECRET_KEY=asdf
        SC_BOOT_MODE=production
        SC_BUILD_TARGET=production
        SC_USER_ID=8004
        SC_USER_NAME=scu
        SHLVL=0
        SIMCORE_SERVICES_NETWORK_NAME=master-simcore_interactive_services_subnet
        STORAGE_ENDPOINT=master_storage:8080
        SWARM_STACK_NAME=master-simcore
        TERM=xterm
        TRACING_OPENTELEMETRY_COLLECTOR_EXPORTER_ENDPOINT=http://jaeger:4318
        TRACING_OPENTELEMETRY_COLLECTOR_SAMPLING_PERCENTAGE=50
        TRAEFIK_SIMCORE_ZONE=master_internal_simcore_stack
        VIRTUAL_ENV=/home/scu/.venv
        LOG_FORMAT_LOCAL_DEV_ENABLED=1
    """,
    )

    settings = ApplicationSettings.create_from_envs()

    assert settings.DIRECTOR_DEFAULT_MAX_MEMORY == 0, "default!"


def test_docker_compose_environment_sample(
    monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict
):

    setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "DEFAULT_MAX_MEMORY": "0",
            "DEFAULT_MAX_NANO_CPUS": "0",
            "DIRECTOR_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS": '{"VRAM": "node.labels.gpu==true"}',
            "DIRECTOR_REGISTRY_CACHING": "True",
            "DIRECTOR_REGISTRY_CACHING_TTL": "00:15:00",
            "DIRECTOR_SELF_SIGNED_SSL_FILENAME": "",
            "DIRECTOR_SELF_SIGNED_SSL_SECRET_ID": "",
            "DIRECTOR_SELF_SIGNED_SSL_SECRET_NAME": "",
            "DIRECTOR_SERVICES_CUSTOM_CONSTRAINTS": "",
            "DIRECTOR_TRACING": "{}",
            "EXTRA_HOSTS_SUFFIX": "undefined",
            "LOGLEVEL": "DEBUG",
            "MONITORING_ENABLED": "True",
            "POSTGRES_DB": "simcoredb",
            "POSTGRES_ENDPOINT": "osparc-dev.foo.com:5432",
            "POSTGRES_HOST": "osparc-dev.foo.com",
            "POSTGRES_PASSWORD": "adsfasdf",
            "POSTGRES_PORT": "5432",
            "POSTGRES_USER": "postgres",
            "PUBLISHED_HOST_NAME": "osparc-master-zmt.click",
            "REGISTRY_AUTH": "True",
            "REGISTRY_PATH": "",
            "REGISTRY_PW": "asdf",
            "REGISTRY_SSL": "True",
            "REGISTRY_URL": "registry.osparc-master-zmt.click",
            "REGISTRY_USER": "admin",
            "SIMCORE_SERVICES_NETWORK_NAME": "master-simcore_interactive_services_subnet",
            "STORAGE_ENDPOINT": "master_storage:8080",
            "SWARM_STACK_NAME": "master-simcore",
            "TRACING_OPENTELEMETRY_COLLECTOR_EXPORTER_ENDPOINT": "http://jaeger:4318",
            "TRACING_OPENTELEMETRY_COLLECTOR_SAMPLING_PERCENTAGE": "50",
            "TRAEFIK_SIMCORE_ZONE": "master_internal_simcore_stack",
        },
    )

    ApplicationSettings.create_from_envs()
