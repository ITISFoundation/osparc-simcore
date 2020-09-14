import logging
from typing import Any, Dict, List

import aiodocker
import yaml
from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import PlainTextResponse

from sidecar import config
from sidecar.storage import store
from sidecar.utils import (
    InvalidComposeSpec,
    assemble_container_name,
    async_command,
    validate_compose_spec,
    write_to_tmp_file,
)

logger = logging.getLogger(__name__)


app = FastAPI()


async def write_file_and_run_command(file_content: str, command: str) -> str:
    """ The command which accepts {file_path} as an argument for string formatting """
    async with write_to_tmp_file(file_content) as file_path:
        return await async_command(
            command.format(
                file_path=file_path,
                project=config.compose_namespace,
                stop_and_remove_timeout=config.stop_and_remove_timeout,
            )
        )


async def remove_the_compose_spec():
    stored_compose_content = await store.get()
    if stored_compose_content is None:
        return True, "No started spec to remove was found"

    command = (
        "docker-compose -p {project} -f {file_path} "
        "down --remove-orphans -t {stop_and_remove_timeout}"
    )
    result = await write_file_and_run_command(
        file_content=stored_compose_content, command=command
    )
    await store.update(None)  # removing compose-file spec
    return result


async def get_container_names():
    compose_file_content = await store.get()
    if compose_file_content is None:
        return []

    parsed_compose_spec = yaml.safe_load(compose_file_content)
    return [
        assemble_container_name(service) for service in parsed_compose_spec["services"]
    ]


@app.on_event("shutdown")
async def shutdown_event():
    await remove_the_compose_spec()
    logger.error("shutdown cleanup completed")


@app.post("/compose/preload", response_class=PlainTextResponse)
async def create_docker_compose_configuration_containers_without_starting(
    request: Request, response: Response
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    body_as_text = (await request.body()).decode("utf-8")

    try:
        validate_compose_spec(body_as_text)
    except InvalidComposeSpec as e:
        response.status_code = 400
        return str(e)

    await store.update(body_as_text)

    # --no-build might be a security risk building is disabled
    command = "docker-compose -p {project} -f {file_path} up --no-build --no-start"

    finished_without_errors, stdout = await write_file_and_run_command(
        file_content=await store.get(), command=command
    )
    response.status_code = 200 if finished_without_errors else 400
    return stdout


@app.put("/compose/stop", response_class=PlainTextResponse)
async def stop_containers_without_removing_them(response: Response) -> str:
    """Stops the previously started service
    and returns the docker-compose output"""
    stored_compose_content = await store.get()
    if stored_compose_content is None:
        response.status_code = 400
        return "No started spec to stop was found"

    command = (
        "docker-compose -p {project} -f {file_path} stop -t {stop_and_remove_timeout}"
    )
    finished_without_errors, stdout = await write_file_and_run_command(
        file_content=stored_compose_content, command=command
    )

    response.status_code = 200 if finished_without_errors else 400
    return stdout


@app.post("/compose", response_class=PlainTextResponse)
async def start_or_update_docker_compose_configuration(
    request: Request, response: Response
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    body_as_text = (await request.body()).decode("utf-8")

    try:
        validate_compose_spec(body_as_text)
    except InvalidComposeSpec as e:
        response.status_code = 400
        return str(e)

    await store.update(body_as_text)

    # --no-build might be a security risk building is disabled
    command = "docker-compose -p {project} -f {file_path} up --no-build -d"

    finished_without_errors, stdout = await write_file_and_run_command(
        file_content=await store.get(), command=command
    )
    response.status_code = 200 if finished_without_errors else 400
    return stdout


@app.delete("/compose", response_class=PlainTextResponse)
async def remove_docker_compose_configuration(response: Response) -> str:
    """Removes the previously started service
    and returns the docker-compose output"""
    finished_without_errors, stdout = await remove_the_compose_spec()
    response.status_code = 200 if finished_without_errors else 400
    return stdout


@app.get("/containers")
async def get_spawned_container_names() -> List[str]:
    """ Returns a list of containers created using docker-compose """
    return await get_container_names()


@app.get("/container/logs")
async def get_container_logs(
    # pylint: disable=unused-argument
    response: Response,
    container: str,
    since: int = Query(
        0,
        title="Timstamp",
        description="Only return logs since this time, as a UNIX timestamp",
    ),
    until: int = Query(
        0,
        title="Timstamp",
        description="Only return logs before this time, as a UNIX timestamp",
    ),
    timestamps: bool = Query(
        False,
        title="Display timestamps",
        description="Enabling this parameter will include timestamps in logs",
    ),
) -> str:
    """ Returns the logs of a given container if found """

    if container not in await get_container_names():
        response.status_code = 400
        return f"No container '{container}' was started"

    docker = aiodocker.Docker()

    try:
        container = await docker.containers.get(container)

        args = dict(stdout=True, stderr=True)
        if timestamps:
            args["timestamps"] = True

        return await container.log(**args)
    except aiodocker.exceptions.DockerError as e:
        response.status_code = 400
        return e.message


@app.get("/container/inspect")
async def container_inspect(response: Response, container: str) -> Dict[str, Any]:
    """ Returns information about the container, like docker inspect command """

    if container not in await get_container_names():
        response.status_code = 400
        return f"No container '{container}' was started"

    docker = aiodocker.Docker()

    try:
        container = await docker.containers.get(container)
        return await container.show()
    except aiodocker.exceptions.DockerError as e:
        response.status_code = 400
        return e.message
