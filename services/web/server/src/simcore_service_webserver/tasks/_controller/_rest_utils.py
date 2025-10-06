from aiohttp import web
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import _URLType, paginate_stream_chunk
from servicelib.celery.models import TaskResultItem
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY


def create_page_response(
    events: list[TaskResultItem], request_url: _URLType, cursor: int, has_more: bool
) -> web.Response:
    page = Page[TaskResultItem].model_validate(
        paginate_stream_chunk(
            chunk=events,
            request_url=request_url,
            cursor=cursor,
            has_more=has_more,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
