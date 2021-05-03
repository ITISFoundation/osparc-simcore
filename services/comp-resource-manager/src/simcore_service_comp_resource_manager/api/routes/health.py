from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from models_library.app_diagnostics import AppStatusCheck

from ..._meta import api_version, project_name
from ..dependencies.application import get_reverse_url_mapper

# from ..dependencies.services import get_api_client

router = APIRouter()


@router.get("/", include_in_schema=False, response_class=PlainTextResponse)
async def check_service_health():
    return f"{__name__}@{datetime.utcnow().isoformat()}"


@router.get("/state", include_in_schema=False)
async def get_service_state(
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    # healths: Tuple[bool] = await asyncio.gather(*[api.is_responsive() for api in apis])

    current_status = AppStatusCheck(
        app_name=project_name,
        version=api_version,
        services={
            # api.service_name: {"healthy": is_healty} for api, is_healty in zip(healths)
        },
        url=url_for("get_service_state"),
    )
    resp = current_status.dict(exclude_unset=True)
    resp.update(docs_dev_url=url_for("swagger_ui_html"))
    return resp
