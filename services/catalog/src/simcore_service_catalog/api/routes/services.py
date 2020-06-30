import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ...models.schemas.service import ServiceOut

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("", response_model=List[ServiceOut])
async def list_services(
    page_token: Optional[str] = Query(
        None, description="Requests a specific page of the list results"
    ),
    page_size: int = Query(
        0, ge=0, description="Maximum number of results to be returned by the server"
    ),
    order_by: Optional[str] = Query(
        None, description="Sorts in ascending order comma-separated fields"
    ),
):
    pass
