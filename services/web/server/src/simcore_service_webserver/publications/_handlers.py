import logging

from aiohttp import MultipartReader, hdrs, web
from common_library.json_serialization import json_dumps
from json2html import json2html  # type: ignore[import-untyped]
from servicelib.aiohttp import status
from servicelib.mimetype_constants import (
    MIMETYPE_APPLICATION_JSON,
    MIMETYPE_APPLICATION_ZIP,
)
from servicelib.request_keys import RQT_USERID_KEY

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..login.storage import AsyncpgStorage, get_plugin_storage
from ..login.utils_email import AttachmentTuple, send_email_from_template, themed
from ..products.api import get_current_product

_logger = logging.getLogger(__name__)

_EMAIL_TEMPLATE_NAME = "service_submission.jinja2"

routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/publications/service-submission", name="service_submission")
@login_required
async def service_submission(request: web.Request):
    product = get_current_product(request)
    reader = MultipartReader.from_response(request)  # type: ignore[arg-type] # PC, IP Whoever is in charge of this. please have a look. this looks very weird
    data = None
    filename = None
    filedata = None

    # Read multipart email
    while True:
        part = await reader.next()  # pylint: disable=not-callable
        if part is None:
            break
        if part.headers[hdrs.CONTENT_TYPE] == MIMETYPE_APPLICATION_JSON:
            data = await part.json()  # type: ignore[union-attr] # PC, IP Whoever is in charge of this. please have a look
            continue
        if part.headers[hdrs.CONTENT_TYPE] == MIMETYPE_APPLICATION_ZIP:
            filedata = await part.read(decode=True)  # type: ignore[union-attr] # PC, IP Whoever is in charge of this. please have a look
            # Validate max file size
            maxsize = 10 * 1024 * 1024  # 10MB
            actualsize = len(filedata)
            if actualsize > maxsize:
                raise web.HTTPRequestEntityTooLarge(maxsize, actualsize)
            filename = part.filename  # type: ignore[union-attr] # PC, IP Whoever is in charge of this. please have a look
            continue
        raise web.HTTPUnsupportedMediaType(
            reason=f"One part had an unexpected type: {part.headers[hdrs.CONTENT_TYPE]}"
        )

    support_email_address = product.support_email

    db: AsyncpgStorage = get_plugin_storage(request.app)
    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    assert user  # nosec
    user_email = user.get("email")
    assert user_email  # nosec

    try:
        attachments = [
            AttachmentTuple(
                filename="metadata.json",
                payload=bytearray(json_dumps(data, indent=4), "utf-8"),
            )
        ]
        if filename and filedata:
            attachments.append(
                AttachmentTuple(
                    filename=filename,
                    payload=bytearray(filedata),
                )
            )
        # send email
        await send_email_from_template(
            request,
            from_=user_email,
            to=support_email_address,
            template=themed("templates/common", _EMAIL_TEMPLATE_NAME),
            context={
                "user": user_email,
                "data": json2html.convert(
                    json=json_dumps(data), table_attributes='class="pure-table"'
                ),
                "subject": "New service submission",
            },
            attachments=attachments,
        )
    except Exception as exc:
        _logger.exception("Error while sending the 'new service submission' mail.")
        raise web.HTTPServiceUnavailable from exc

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
