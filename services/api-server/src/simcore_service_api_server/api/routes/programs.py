from collections.abc import Callable
from operator import attrgetter
from typing import Annotated

from fastapi import APIRouter, Depends
from servicelib.fastapi.dependencies import get_reverse_url_mapper

from ...models.schemas.programs import Program
from ...services_http.catalog import CatalogApi
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.services import get_api_client

router = APIRouter()


@router.get("", response_model=list[Program])
async def list_programs(
    user_id: Annotated[int, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    """Lists all available solvers (latest version)

    SEE get_solvers_page for paginated version of this function
    """
    solvers: list[Program] = await catalog_client.list_programs(
        user_id=user_id, product_name=product_name
    )

    # for solver in solvers:
    #     solver.url = url_for(
    #         "get_solver_release", solver_key=solver.id, version=solver.version
    #     )

    return sorted(solvers, key=attrgetter("id"))
