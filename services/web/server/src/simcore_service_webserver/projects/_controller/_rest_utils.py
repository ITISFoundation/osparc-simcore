from aiohttp import web
from models_library.api_schemas_webserver.projects import ProjectListItem
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from yarl import URL

from .. import _permalink_service
from .._crud_api_read import _paralell_update
from ..models import ProjectDict


async def aggregate_data_to_projects_from_request(
    app: web.Application,
    url: URL,
    headers: dict[str, str],
    projects: list[ProjectDict],
) -> list[ProjectDict]:

    update_permalink_per_project = [
        # permalink
        _permalink_service.aggregate_permalink_in_project(
            app, url, headers, project=prj
        )
        for prj in projects
    ]

    updated_projects: list[ProjectDict] = await _paralell_update(
        *update_permalink_per_project,
    )
    return updated_projects


def create_page_response(projects, request_url, total, limit, offset) -> web.Response:
    page = Page[ProjectListItem].model_validate(
        paginate_data(
            chunk=[
                ProjectListItem.from_domain_model(prj).model_dump(
                    by_alias=True, exclude_unset=True
                )
                for prj in projects
            ],
            request_url=request_url,
            total=total,
            limit=limit,
            offset=offset,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
