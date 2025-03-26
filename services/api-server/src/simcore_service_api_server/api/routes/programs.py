from collections.abc import Callable
from operator import attrgetter
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from httpx import HTTPStatusError
from pydantic import ValidationError
from servicelib.fastapi.dependencies import get_reverse_url_mapper

from ...models.schemas.programs import Program, ProgramKeyId, VersionStr
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
    programs = await catalog_client.list_programs(
        user_id=user_id, product_name=product_name
    )

    for program in programs:
        program.url = url_for(
            "get_program_release", program_key=program.id, version=program.version
        )

    return sorted(programs, key=attrgetter("id"))


@router.get(
    "/{program_key:path}/releases/{version}",
    response_model=Program,
)
async def get_program_release(
    program_key: ProgramKeyId,
    version: VersionStr,
    user_id: Annotated[int, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
) -> Program:
    """Gets a specific release of a solver"""
    try:
        program = await catalog_client.get_program(
            user_id=user_id,
            name=program_key,
            version=version,
            product_name=product_name,
        )

        program.url = url_for(
            "get_program_release", program_key=program.id, version=program.version
        )
        return program

    except (
        ValueError,
        IndexError,
        ValidationError,
        HTTPStatusError,
    ) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Program {program_key}:{version} not found",
        ) from err
