import functools
import logging
import uuid as uuidlib
from operator import attrgetter
from typing import Callable, Dict, List, Optional
from uuid import UUID

import packaging.version
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from starlette import status

from ...models.schemas.solvers import (
    LATEST_VERSION,
    Job,
    JobInput,
    JobOutput,
    JobState,
    KeyIdentifier,
    Solver,
    SolverImageName,
    SolverOutput,
)
from ...modules.catalog import CatalogApi
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.services import get_api_client
from .solvers_fake import FAKE

# from urllib.request import pathname2url
# from fastapi.responses import RedirectResponse
logger = logging.getLogger(__name__)

router = APIRouter()


## SOLVERS -----------------------------------------------------------------------------------------


@router.get("", response_model=List[Solver])
async def list_solvers(
    _catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """
    Returns a list of the latest version of each solver
    """
    latest_solvers = [
        Solver(
            solver_url=url_for(
                "get_solver_by_id",
                solver_id=data["uuid"],
            ),
            **data,
        )
        for data in FAKE.solvers
    ]

    return sorted(latest_solvers, key=attrgetter("name"))


@router.get("/{solver_name:path}/{version}", response_model=Solver)
async def get_solver_by_name_and_version(
    solver_name: SolverImageName,
    version: str,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    try:
        if version == LATEST_VERSION:
            data = FAKE.get_latest(solver_name)
        else:
            data = FAKE.get2(solver_name, version)

    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from err

    return Solver(
        solver_url=url_for(
            "get_solver_by_id",
            solver_id=data["uuid"],
        ),
        **data,
    )

    # catalog get / key:latest
    # raise NotImplementedError(f"GET {solver_name}:{version}")
    # raise NotImplementedError(f"GET latest {solver_name}")


@router.get("/{solver_id}", response_model=Solver)
async def get_solver_by_id(
    solver_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    try:
        data = FAKE.get(str(solver_id))
        return Solver(
            solver_url=url_for(
                "get_solver_by_id",
                solver_id=data["uuid"],
            ),
            **data,
        )
    except KeyError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from err

    # catalog get /image_id
    # raise NotImplementedError(f"GET solver {solver_id}")


async def _list_solvers_impl(
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    # TODO: pagination
    # TODO: deduce user
    # filter and format as in docker listings ??

    # FIXME: temporary hard-coded user!
    user_id = 1

    available_services = await catalog_client.get(
        "/services",
        params={"user_id": user_id, "details": False},
        headers={"x-simcore-products-name": "osparc"},
    )

    # TODO: move this sorting down to database?
    # Create list list of the latest version of each solver
    latest_solvers: Dict[str, Solver] = {}
    for service in available_services:
        if service["type"] == "computational":
            service_key = service["key"]

            solver = latest_solvers.get(service_key)

            if not solver or packaging.version.parse(
                solver.version
            ) < packaging.version.parse(service["version"]):
                try:
                    # FIXME: image id is not provided. Temp fake id
                    image_uuid = compose_solver_id(service_key, service["version"])

                    latest_solvers[service_key] = Solver(
                        uuid=image_uuid,
                        name=service_key,
                        title=service["name"],
                        maintainer=service["contact"],
                        version=service["version"],
                        description=service.get("description"),
                        # solver_url=url_for(
                        #    "get_solver_by_name_and_version",
                        #    solver_name=pathname2url(service_key),
                        #    version=service["version"],
                        # ),
                        solver_url=url_for(
                            "get_solver_by_id",
                            solver_id=image_uuid,
                        ),
                        # TODO: if field is not set in service, do not set here
                    )
                except ValidationError as err:
                    # NOTE: This is necessary because there are no guarantees
                    #       at the image registry. Therefore we exclude and warn
                    #       invalid items instead of returning error
                    logger.warning(
                        "Skipping invalid service returned by catalog '%s': %s",
                        service_key,
                        err,
                    )
                except (KeyError, IndexError) as err:
                    logger.error("API catalog response required fields did change!")
                    raise HTTPException(
                        status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Catalog API corrupted",
                    ) from err

    return sorted(latest_solvers.values(), key=attrgetter("name"))


# HELPERS ----

NAMESPACE_SOLVER_KEY = uuidlib.UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")


@functools.lru_cache()
def compose_solver_id(solver_key: SolverImageName, version: str) -> UUID:
    # FIXME: this is a temporary solution. Should be image id

    return uuidlib.uuid3(NAMESPACE_SOLVER_KEY, f"{solver_key}:{version}")
