# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import aiodocker
import docker
import jsonschema
import pytest
import tenacity
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.docker_registry import RegistrySettings

from .helpers.host import get_localhost_ip

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def docker_registry(keep_docker_up: bool) -> Iterator[str]:
    """sets up and runs a docker registry container locally and returns its URL"""
    # run the registry outside of the stack
    docker_client = docker.from_env()
    # try to login to private registry
    host = "127.0.0.1"
    port = 5000
    url = f"{host}:{port}"
    container = None
    try:
        docker_client.login(registry=url, username="simcore")
        container = docker_client.containers.list(filters={"name": "pytest_registry"})[
            0
        ]
        print("Warning: docker registry is already up!")
    except Exception:  # pylint: disable=broad-except
        container = docker_client.containers.run(
            "registry:2",
            ports={"5000": "5000"},
            name="pytest_registry",
            environment=["REGISTRY_STORAGE_DELETE_ENABLED=true"],
            restart_policy={"Name": "always"},
            volumes={
                "pytest_registry_data": {"bind": "/var/lib/registry", "mode": "rw"}
            },
            detach=True,
        )

        # Wait until we can connect
        assert wait_till_registry_is_responsive(url)

    # get the hello world example from docker hub
    hello_world_image = docker_client.images.pull("hello-world", "latest")
    # login to private registry
    docker_client.login(registry=url, username="simcore")
    # tag the image
    repo = url + "/hello-world:dev"
    assert hello_world_image.tag(repo) == True
    # push the image to the private registry
    docker_client.images.push(repo)
    # wipe the images
    docker_client.images.remove(image="hello-world:latest")
    docker_client.images.remove(image=hello_world_image.id)
    # pull the image from the private registry
    private_image = docker_client.images.pull(repo)
    docker_client.images.remove(image=private_image.id)

    # provide os.environs
    # TODO: use monkey-patch
    old = deepcopy(os.environ)
    os.environ["REGISTRY_SSL"] = "False"
    os.environ["REGISTRY_AUTH"] = "False"
    # the registry URL is how to access from the container (e.g. for accessing the API)
    os.environ["REGISTRY_URL"] = f"{get_localhost_ip()}:5000"
    # the registry PATH is how the docker engine shall access the images (usually same as REGISTRY_URL but for testing)
    os.environ["REGISTRY_PATH"] = "127.0.0.1:5000"
    os.environ["REGISTRY_USER"] = "simcore"
    os.environ["REGISTRY_PW"] = ""

    yield url

    # restore environs
    os.environ = old

    # remove registry
    if not keep_docker_up:
        container.stop()
        container.remove(force=True)

        while docker_client.containers.list(filters={"name": container.name}):
            time.sleep(1)


@pytest.fixture
def external_registry_settings(
    external_envfile_dict: EnvVarsDict,
) -> RegistrySettings | None:
    if external_envfile_dict:
        config = {
            field: external_envfile_dict.get(field, None)
            for field in RegistrySettings.model_fields
        }
        return RegistrySettings.model_validate(config)
    return None


@pytest.fixture
def registry_settings(
    docker_registry: str, external_registry_settings: RegistrySettings | None
) -> RegistrySettings:
    if external_registry_settings:
        return external_registry_settings
    return RegistrySettings.create_from_envs()


@tenacity.retry(
    wait=tenacity.wait_fixed(2),
    stop=tenacity.stop_after_delay(20),
    before_sleep=tenacity.before_sleep_log(log, logging.INFO),
    reraise=True,
)
def wait_till_registry_is_responsive(url: str) -> bool:
    docker_client = docker.from_env()
    docker_client.login(registry=url, username="simcore")
    return True


# ********************************************************* Services ***************************************


def _pull_push_service(
    pull_key: str,
    tag: str,
    new_registry: str,
    node_meta_schema: dict,
    owner_email: str | None = None,
) -> dict[str, Any]:
    client = docker.from_env()
    # pull image from original location
    print(f"Pulling {pull_key}:{tag} ...")
    image = client.images.pull(pull_key, tag=tag)
    assert image, f"image {pull_key}:{tag} could NOT be pulled!"

    # get io.simcore.* labels
    image_labels: dict = dict(image.labels)

    if owner_email:
        print(f"Overriding labels to take ownership as {owner_email} ...")
        # By overriding these labels, user owner_email gets ownership of the service
        # and the catalog service automatically gives full access rights for testing it
        # otherwise it does not even get read rights

        image_labels.update({"io.simcore.contact": f'{{"contact": "{owner_email}"}}'})
        image_labels.update(
            {
                "io.simcore.authors": f'{{"authors": [{{"name": "Tester", "email": "{owner_email}", "affiliation": "IT\'IS Foundation"}}] }}'
            }
        )
        image_labels.update({"maintainer": f"{owner_email}"})

        df_path = Path("Dockerfile").resolve()
        df_path.write_text(f"FROM {pull_key}:{tag}")

        try:
            # Rebuild to override image labels AND re-tag
            image2, _ = client.images.build(
                path=str(df_path.parent), labels=image_labels, tag=f"{tag}-owned"
            )
            print(json.dumps(image2.labels, indent=2))
            image = image2

        finally:
            df_path.unlink()

    assert image_labels
    io_simcore_labels = {
        key[len("io.simcore.") :]: json.loads(value)[key[len("io.simcore.") :]]
        for key, value in image_labels.items()
        if key.startswith("io.simcore.")
    }
    assert io_simcore_labels

    # validate image
    jsonschema.validate(io_simcore_labels, node_meta_schema)

    # tag image
    new_image_tag = (
        f"{new_registry}/{io_simcore_labels['key']}:{io_simcore_labels['version']}"
    )
    assert image.tag(new_image_tag) == True

    # push the image to the new location
    print(f"Pushing {pull_key}:{tag}  -> {new_image_tag}...")
    client.images.push(new_image_tag)

    # return image io.simcore.* labels
    image_labels = dict(image.labels)
    return {
        "schema": io_simcore_labels,
        "image": {
            "name": f"{io_simcore_labels['key']}",
            "tag": io_simcore_labels["version"],
        },
    }


@pytest.fixture(scope="session")
def docker_registry_image_injector(
    docker_registry: str, node_meta_schema: dict
) -> Callable[..., dict[str, Any]]:
    def inject_image(
        source_image_repo: str, source_image_tag: str, owner_email: str | None = None
    ):
        return _pull_push_service(
            source_image_repo,
            source_image_tag,
            docker_registry,
            node_meta_schema,
            owner_email,
        )

    return inject_image


@pytest.fixture
def osparc_service(
    docker_registry: str, node_meta_schema: dict, service_repo: str, service_tag: str
) -> dict[str, Any]:
    """pulls the service from service_repo:service_tag and pushes to docker_registry using the oSparc node meta schema
    NOTE: 'service_repo' and 'service_tag' defined as parametrization
    """
    return _pull_push_service(
        service_repo, service_tag, docker_registry, node_meta_schema
    )


@pytest.fixture(scope="session")
def sleeper_service(docker_registry: str, node_meta_schema: dict) -> dict[str, Any]:
    """Adds a itisfoundation/sleeper in docker registry"""
    return _pull_push_service(
        "itisfoundation/sleeper", "1.0.0", docker_registry, node_meta_schema
    )


@pytest.fixture(scope="session")
def jupyter_service(docker_registry: str, node_meta_schema: dict) -> dict[str, Any]:
    """Adds a itisfoundation/jupyter-base-notebook in docker registry"""
    return _pull_push_service(
        "itisfoundation/jupyter-base-notebook",
        "2.13.0",
        docker_registry,
        node_meta_schema,
    )


@pytest.fixture(scope="session", params=["2.0.7"])
def dy_static_file_server_version(request: pytest.FixtureRequest):
    return request.param


@pytest.fixture(scope="session")
def dy_static_file_server_service(
    docker_registry: str, node_meta_schema: dict, dy_static_file_server_version: str
) -> dict[str, Any]:
    """
    Adds the below service in docker registry
    itisfoundation/dy-static-file-server
    """
    return _pull_push_service(
        "itisfoundation/dy-static-file-server",
        dy_static_file_server_version,
        docker_registry,
        node_meta_schema,
    )


@pytest.fixture(scope="session")
def dy_static_file_server_dynamic_sidecar_service(
    docker_registry: str, node_meta_schema: dict, dy_static_file_server_version: str
) -> dict[str, Any]:
    """
    Adds the below service in docker registry
    itisfoundation/dy-static-file-server-dynamic-sidecar
    """
    return _pull_push_service(
        "itisfoundation/dy-static-file-server-dynamic-sidecar",
        dy_static_file_server_version,
        docker_registry,
        node_meta_schema,
    )


@pytest.fixture(scope="session")
def dy_static_file_server_dynamic_sidecar_compose_spec_service(
    docker_registry: str, node_meta_schema: dict, dy_static_file_server_version: str
) -> dict[str, Any]:
    """
    Adds the below service in docker registry
    itisfoundation/dy-static-file-server-dynamic-sidecar-compose-spec
    """
    return _pull_push_service(
        "itisfoundation/dy-static-file-server-dynamic-sidecar-compose-spec",
        dy_static_file_server_version,
        docker_registry,
        node_meta_schema,
    )


@pytest.fixture
def remove_images_from_host() -> Callable[[list[str]], Awaitable[None]]:
    async def _cleaner(images: list[str]) -> None:
        with log_context(
            logging.INFO, msg=(f"removing {images=}", f"removed {images=}")
        ):
            async with aiodocker.Docker() as client:
                delete_results = await asyncio.gather(
                    *(client.images.delete(image, force=True) for image in images),
                    return_exceptions=True,
                )
                assert delete_results
                # confirm they are gone
                inspect_results = await asyncio.gather(
                    *(client.images.inspect(image) for image in images),
                    return_exceptions=True,
                )
                assert all(
                    isinstance(r, aiodocker.DockerError) for r in inspect_results
                )

    return _cleaner
