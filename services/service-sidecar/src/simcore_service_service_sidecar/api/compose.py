from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

from ..settings import ServiceSidecarSettings
from ..shared_handlers import remove_the_compose_spec, write_file_and_run_command
from ..storage import SharedStore
from ..utils import InvalidComposeSpec

compose_router = APIRouter()


@compose_router.post(
    "/compose:store", response_class=PlainTextResponse, responses={204: {"model": None}}
)
async def store_docker_compose_spec_for_later_usage(
    request: Request, response: Response
) -> None:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    body_as_text = (await request.body()).decode("utf-8")

    shared_store: SharedStore = request.app.state.shared_store

    try:
        shared_store.put_spec(body_as_text)
    except InvalidComposeSpec as e:
        response.status_code = 400
        return str(e)

    response.status_code = 204
    return None


@compose_router.post("/compose:preload", response_class=PlainTextResponse)
async def create_docker_compose_configuration_containers_without_starting(
    request: Request, response: Response, command_timeout: float
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    body_as_text = (await request.body()).decode("utf-8")

    settings: ServiceSidecarSettings = request.app.state.settings

    shared_store: SharedStore = request.app.state.shared_store

    try:
        shared_store.put_spec(body_as_text)
    except InvalidComposeSpec as e:
        response.status_code = 400
        return str(e)

    # --no-build might be a security risk building is disabled
    command = "docker-compose -p {project} -f {file_path} up --no-build --no-start"
    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings,
        file_content=shared_store.get_spec(),
        command=command,
        command_timeout=command_timeout,
    )

    response.status_code = 200 if finished_without_errors else 400
    return stdout


@compose_router.put("/compose:stop", response_class=PlainTextResponse)
async def stop_containers_without_removing_them(
    request: Request, response: Response, command_timeout: float
) -> str:
    """Stops the previously started service
    and returns the docker-compose output"""
    shared_store: SharedStore = request.app.state.shared_store
    settings: ServiceSidecarSettings = request.app.state.settings

    stored_compose_content = shared_store.get_spec()
    if stored_compose_content is None:
        response.status_code = 400
        return "No started spec to stop was found"

    command = (
        "docker-compose -p {project} -f {file_path} stop -t {stop_and_remove_timeout}"
    )
    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings,
        file_content=stored_compose_content,
        command=command,
        command_timeout=command_timeout,
    )

    response.status_code = 200 if finished_without_errors else 400
    return stdout


@compose_router.get("/compose:pull", response_class=PlainTextResponse)
async def pull_docker_required_docker_images(
    request: Request, response: Response, command_timeout: float
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    shared_store: SharedStore = request.app.state.shared_store
    settings: ServiceSidecarSettings = request.app.state.settings

    stored_compose_content = shared_store.get_spec()
    if stored_compose_content is None:
        response.status_code = 400
        return "No started spec to stop was found"

    command = "docker-compose -p {project} -f {file_path} pull --include-deps"

    try:
        # mark as pulling images
        shared_store.set_is_pulling_containsers()

        finished_without_errors, stdout = await write_file_and_run_command(
            settings=settings,
            file_content=stored_compose_content,
            command=command,
            command_timeout=command_timeout,
        )
    finally:
        # remove mark
        shared_store.unset_is_pulling_containsers()

    response.status_code = 200 if finished_without_errors else 400
    return stdout


@compose_router.post("/compose", response_class=PlainTextResponse)
async def start_or_update_docker_compose_configuration(
    request: Request, response: Response, command_timeout: float
) -> str:
    """ Expects the docker-compose spec as raw-body utf-8 encoded text """
    settings: ServiceSidecarSettings = request.app.state.settings
    shared_store: SharedStore = request.app.state.shared_store

    # --no-build might be a security risk building is disabled
    command = "docker-compose -p {project} -f {file_path} up --no-build -d"
    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings,
        file_content=shared_store.get_spec(),
        command=command,
        command_timeout=command_timeout,
    )

    response.status_code = 200 if finished_without_errors else 400
    return stdout


@compose_router.delete("/compose", response_class=PlainTextResponse)
async def remove_docker_compose_configuration(
    request: Request, response: Response, command_timeout: float
) -> str:
    """Removes the previously started service
    and returns the docker-compose output"""
    finished_without_errors, stdout = await remove_the_compose_spec(
        shared_store=request.app.state.shared_store,
        settings=request.app.settings,
        command_timeout=command_timeout,
    )

    response.status_code = 200 if finished_without_errors else 400
    return stdout


__all__ = ["compose_router"]
