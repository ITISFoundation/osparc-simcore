# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import filecmp
import json
import os
import shutil
import urllib.request
from contextlib import suppress
from pathlib import Path
from pprint import pformat
from typing import Dict, Iterator, Optional

import docker
import jsonschema
import pytest
import yaml
from docker.errors import APIError
from docker.models.containers import Container

_FOLDER_NAMES = ["input", "output"]

## FIXME: 'Not all images have this home directory. Why impose it? Maybe I am mistaken but I do not understand what this var refers to.' by ANE
_CONTAINER_FOLDER = Path("/home/scu/data")


@pytest.fixture
def docker_client() -> docker.DockerClient:
    return docker.from_env()


@pytest.fixture
def docker_image_key(docker_client: docker.DockerClient, project_name: str) -> str:
    image_key = f"{project_name}:"
    docker_images = [
        image
        for image in docker_client.images.list()
        if any(image_key in tag for tag in image.tags)
    ]
    return docker_images[0].tags[0]


@pytest.fixture
def docker_image(
    docker_client: docker.DockerClient, docker_image_key: str
) -> docker.models.images.Image:
    docker_image = docker_client.images.get(docker_image_key)
    assert docker_image
    return docker_image


@pytest.fixture
def temporary_path(tmp_path: Path) -> Path:
    def _is_gitlab_executor() -> bool:
        return "GITLAB_CI" in os.environ

    if _is_gitlab_executor():
        # /builds is a path that is shared between the docker in docker container and the job builder container
        shared_path = Path("/builds/{}/tmp".format(os.environ["CI_PROJECT_PATH"]))
        shared_path.mkdir(parents=True, exist_ok=True)
        return shared_path
    return tmp_path


# FIXTURES
@pytest.fixture
def osparc_service_labels_jsonschema(tmp_path) -> Dict:
    def _download_url(url: str, file: Path):
        # Download the file from `url` and save it locally under `file_name`:
        with urllib.request.urlopen(url) as response, file.open("wb") as out_file:
            shutil.copyfileobj(response, out_file)
        assert file.exists()

    url = "https://raw.githubusercontent.com/ITISFoundation/osparc-simcore/master/api/specs/common/schemas/node-meta-v0.0.1.json"
    # TODO: Make sure this is installed with this package!!!

    file_name = tmp_path / "service_label.json"
    _download_url(url, file_name)
    with file_name.open() as fp:
        json_schema = json.load(fp)
        return json_schema


@pytest.fixture(scope="session")
def metadata_labels(metadata_file: Path) -> Dict:
    with metadata_file.open() as fp:
        metadata = yaml.safe_load(fp)
        return metadata


@pytest.fixture
def host_folders(temporary_path: Path) -> Dict:
    tmp_dir = temporary_path

    host_folders = {}
    for folder in _FOLDER_NAMES:
        path = tmp_dir / folder
        if path.exists():
            shutil.rmtree(path)
        path.mkdir()
        # we need to ensure the path is writable for the docker container (Gitlab-CI case)
        os.chmod(str(path), 0o775)
        assert path.exists()
        host_folders[folder] = path

    return host_folders


@pytest.fixture
def container_variables() -> Dict:
    # of type INPUT_FOLDER=/home/scu/data/input
    env = {
        "{}_FOLDER".format(str(folder).upper()): (_CONTAINER_FOLDER / folder).as_posix()
        for folder in _FOLDER_NAMES
    }
    return env


@pytest.fixture
def validation_folders(validation_dir: Path) -> Dict:
    return {folder: (validation_dir / folder) for folder in _FOLDER_NAMES}


@pytest.fixture
def docker_container(
    validation_folders: Dict,
    host_folders: Dict,
    docker_client: docker.DockerClient,
    docker_image_key: str,
    container_variables: Dict,
) -> Iterator[Container]:
    # copy files to input folder, copytree needs to not have the input folder around.
    host_folders["input"].rmdir()
    shutil.copytree(validation_folders["input"], host_folders["input"])
    assert Path(host_folders["input"]).exists()
    # run the container (this may take some time)
    container: Optional[Container] = None
    try:
        volumes = {
            host_folders[folder]: {
                "bind": container_variables["{}_FOLDER".format(str(folder).upper())]
            }
            for folder in _FOLDER_NAMES
        }
        container = docker_client.containers.run(
            docker_image_key,
            "run",
            detach=True,
            remove=False,
            volumes=volumes,
            environment=container_variables,
        )
        response = container.wait()
        if response["StatusCode"] > 0:
            logs = container.logs(timestamps=True, tail=1000)
            pytest.fail(
                "The container stopped with exit code {}\n\n\ncommand:\n {}, \n\n\nlog:\n{}".format(
                    response["StatusCode"],
                    "run",
                    pformat(
                        (logs.decode("UTF-8")).split("\n"),
                        width=200,
                    ),
                )
            )
        else:

            yield container

    except docker.errors.ContainerError as exc:
        # the container did not run correctly
        pytest.fail(
            "The container stopped with exit code {}\n\n\ncommand:\n {}, \n\n\nlog:\n{}".format(
                exc.exit_status,
                exc.command,
                pformat(
                    (container.logs(timestamps=True, tail=1000).decode("UTF-8")).split(
                        "\n"
                    ),
                    width=200,
                )
                if container
                else "",
            )
        )
    finally:
        # cleanup
        if container:
            with suppress(APIError):
                container.remove()


# HELPERS --------------------


def convert_to_simcore_labels(image_labels: Dict) -> Dict:
    io_simcore_labels = {}
    for key, value in image_labels.items():
        if str(key).startswith("io.simcore."):
            simcore_label = json.loads(value)
            simcore_keys = list(simcore_label.keys())
            assert len(simcore_keys) == 1
            simcore_key = simcore_keys[0]
            simcore_value = simcore_label[simcore_key]
            io_simcore_labels[simcore_key] = simcore_value
    assert len(io_simcore_labels) > 0
    return io_simcore_labels


def assert_container_runs(
    validation_folders: Dict,
    host_folders: Dict,
    docker_container: Container,
):
    for folder in _FOLDER_NAMES:
        # test if the files that should be there are actually there and correct
        list_of_files = [
            x.name
            for x in validation_folders[folder].iterdir()
            if not ".gitkeep" in x.name
        ]
        for file_name in list_of_files:
            assert Path(
                host_folders[folder] / file_name
            ).exists(), f"{file_name} is missing from {host_folders[folder]}"

        # we look for missing files only. contents is the responsibility of the service creator
        _, _, errors = filecmp.cmpfiles(
            host_folders[folder],
            validation_folders[folder],
            list_of_files,
            shallow=True,
        )
        assert not errors, f"{errors} are missing in {host_folders[folder]}"

        if folder == "input":
            continue
        # test if the generated files are the ones expected
        list_of_files = [
            x.name for x in host_folders[folder].iterdir() if not ".gitkeep" in x.name
        ]
        for file_name in list_of_files:
            assert Path(
                validation_folders[folder] / file_name
            ).exists(), "{} is not present in {}".format(
                file_name, validation_folders[folder]
            )
        _, _, errors = filecmp.cmpfiles(
            host_folders[folder],
            validation_folders[folder],
            list_of_files,
            shallow=False,
        )
        # assert not mismatch, "wrong/incorrect generated files in {}".format(host_folders[folder])
        assert not errors, f"{errors} should not be available in {host_folders[folder]}"

    # check the output is correct based on container labels
    output_cfg = {}
    output_cfg_file = Path(host_folders["output"] / "outputs.json")
    if output_cfg_file.exists():
        with output_cfg_file.open() as fp:
            output_cfg = json.load(fp)

    container_labels = docker_container.labels
    io_simcore_labels = convert_to_simcore_labels(container_labels)
    assert "outputs" in io_simcore_labels
    for key, value in io_simcore_labels["outputs"].items():
        assert "type" in value
        # rationale: files are on their own and other types are in inputs.json
        if not "data:" in value["type"]:
            # check that keys are available
            assert key in output_cfg
        else:
            # it's a file and it should be in the folder as well using key as the filename
            filename_to_look_for = key
            if "fileToKeyMap" in value:
                # ...or there is a mapping
                assert len(value["fileToKeyMap"]) > 0
                for filename, mapped_value in value["fileToKeyMap"].items():
                    assert mapped_value == key
                    filename_to_look_for = filename
            assert (host_folders["output"] / filename_to_look_for).exists()


def assert_docker_io_simcore_labels_against_files(
    docker_image: docker.models.images.Image, metadata_labels: Dict
):
    image_labels = docker_image.labels
    io_simcore_labels = convert_to_simcore_labels(image_labels)
    # check files are identical
    for key, value in io_simcore_labels.items():
        assert key in metadata_labels
        assert value == metadata_labels[key]


def assert_validate_docker_io_simcore_labels(
    docker_image: docker.models.images.Image, osparc_service_labels_jsonschema: Dict
):
    image_labels = docker_image.labels
    # get io labels
    io_simcore_labels = convert_to_simcore_labels(image_labels)
    # validate schema
    try:
        jsonschema.validate(io_simcore_labels, osparc_service_labels_jsonschema)
    except jsonschema.SchemaError:
        pytest.fail(
            "Schema {} contains errors".format(osparc_service_labels_jsonschema)
        )
    except jsonschema.ValidationError:
        pytest.fail("Failed to validate docker image io labels against schema")
