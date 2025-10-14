from aiohttp import web
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import _URLType, paginate_stream_chunk
from servicelib.celery.models import TaskStreamItem
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY


def create_page_response(
    items: list[TaskStreamItem],
    request_url: _URLType,
) -> web.Response:
    page = Page[TaskStreamItem].model_validate(
        paginate_stream_chunk(
            chunk=items,
            request_url=request_url,
            cursor=0,
            has_more=True,
        )
    )
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )
