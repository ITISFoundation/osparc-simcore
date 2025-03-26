from models_library.basic_types import VersionStr
from models_library.products import ProductName
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageOffsetInt,
)
from models_library.users import UserID

from ..models.schemas.solvers import Solver, SolverKeyId, SolverPort

_FAKE: list[Solver] = [
    Solver.model_validate(Solver.model_json_schema()["example"]),
]
_FAKE2: list[SolverPort] = [
    SolverPort.model_validate(SolverPort.model_json_schema()["example"]),
]


async def list_latest_releases(
    *,
    product_name: ProductName,
    user_id: UserID,
    offset: PageOffsetInt = 0,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
) -> list[Solver]:
    assert product_name  # nosec
    assert user_id  # nosec

    return _FAKE[offset : offset + limit]


async def list_solver_releases(
    *,
    product_name: ProductName,
    user_id: UserID,
    solver_id: SolverKeyId,
    offset: PageOffsetInt = 0,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
) -> list[Solver]:
    assert product_name  # nosec
    assert user_id  # nosec
    return [solver for solver in _FAKE if solver.id == solver_id][
        offset : offset + limit
    ]


async def get_solver(
    *,
    product_name: ProductName,
    user_id: UserID,
    solver_id: SolverKeyId,
    solver_version: VersionStr,
) -> Solver | None:
    assert product_name  # nosec
    assert user_id  # nosec

    return next(
        (
            solver
            for solver in _FAKE
            if solver.id == solver_id and solver.version == solver_version
        ),
        None,
    )


async def get_solver_ports(
    *,
    product_name: ProductName,
    user_id: int,
    solver_id: SolverKeyId,
    solver_version: VersionStr,
) -> list[SolverPort]:

    if await get_solver(
        product_name=product_name,
        user_id=user_id,
        solver_id=solver_id,
        solver_version=solver_version,
    ):
        return _FAKE2
    return []
