import logging
from typing import Callable, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from ...models.schemas.solvers import LATEST_VERSION, Solver, SolverName
from ..dependencies.application import get_reverse_url_mapper
from .solvers_faker import the_fake_impl

logger = logging.getLogger(__name__)

router = APIRouter()


## SOLVERS -----------------------------------------------------------------------------------------


@router.get("", response_model=List[Solver])
async def list_solvers(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    def _url_resolver(solver_id: UUID):
        return url_for(
            "get_solver",
            solver_id=solver_id,
        )

    # TODO: Consider sorted(latest_solvers, key=attrgetter("name", "version"))
    return list(the_fake_impl.values(_url_resolver))


@router.get("/{solver_id}", response_model=Solver)
async def get_solver(
    solver_id: UUID,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    try:
        solver = the_fake_impl.get(
            solver_id,
            url=url_for(
                "get_solver",
                solver_id=solver_id,
            ),
        )
        return solver

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver {solver_id} not found",
        ) from err


@router.get("/{solver_name:path}/{version}", response_model=Solver)
async def get_solver_by_name_and_version(
    solver_name: SolverName,
    version: str,
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    try:

        def _url_resolver(solver_id: UUID):
            return url_for(
                "get_solver",
                solver_id=solver_id,
            )

        if version == LATEST_VERSION:
            solver = the_fake_impl.get_latest(solver_name, _url_resolver)
        else:
            solver = the_fake_impl.get_by_name_and_version(
                solver_name, version, _url_resolver
            )
        return solver

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Solver {solver_name}:{version} not found",
        ) from err
