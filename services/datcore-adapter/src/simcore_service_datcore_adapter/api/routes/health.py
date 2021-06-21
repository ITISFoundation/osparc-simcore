import logging
from datetime import datetime

from fastapi import APIRouter
from starlette import status
from starlette.responses import PlainTextResponse

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/health",
    summary="return service health",
    response_model=PlainTextResponse,
    status_code=status.HTTP_200_OK,
)
async def get_service_status():
    return f"{__name__}@{datetime.utcnow().isoformat()}"


# @router.get("/state")
# async def get_service_state(
#     datcore_client: CatalogApi = Depends(get_api_client(CatalogApi)),
#     url_for: Callable = Depends(get_reverse_url_mapper),
# ):
#     apis = (catalog_client, director2_api, storage_client, webserver_client)
#     heaths: Tuple[bool] = await asyncio.gather(*[api.is_responsive() for api in apis])

#     current_status = AppStatusCheck(
#         app_name=project_name,
#         version=api_version,
#         services={
#             api.service_name: {
#                 "healthy": is_healty,
#                 "url": str(api.client.base_url) + api.health_check_path.lstrip("/"),
#             }
#             for api, is_healty in zip(apis, heaths)
#         },
#         url=url_for("get_service_state"),
#     )
#     resp = current_status.dict(exclude_unset=True)
#     resp.update(docs_dev_url=url_for("swagger_ui_html"))
#     return resp
