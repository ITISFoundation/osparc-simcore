import json
import logging
import os

from aiohttp import MultipartReader, hdrs, web
from json2html import json2html
from servicelib.request_keys import RQT_USERID_KEY

from .email_settings import SMTPSettings
from .email_settings import get_plugin_settings as get_email_settings
from .login.decorators import login_required
from .login.storage import AsyncpgStorage, get_plugin_storage
from .login.utils_email import themed

log = logging.getLogger(__name__)

EMAIL_TEMPLATE_NAME = "service_submission.jinja2"


@login_required
async def service_submission(request: web.Request):
    reader = MultipartReader.from_response(request)
    data = None
    filedata = None

    # Read multipart email
    while True:
        part = await reader.next()  # pylint: disable=not-callable
        if part is None:
            break
        if part.headers[hdrs.CONTENT_TYPE] == "application/json":
            data = await part.json()
            continue
        if part.headers[hdrs.CONTENT_TYPE] == "application/zip":
            filedata = await part.read(decode=True)
            # Validate max file size
            maxsize = 10 * 1024 * 1024  # 10MB
            actualsize = len(filedata)
            if actualsize > maxsize:
                raise web.HTTPRequestEntityTooLarge(maxsize, actualsize)
            filename = part.filename
            continue
        raise web.HTTPUnsupportedMediaType(
            reason=f"One part had an unexpected type: {part.headers[hdrs.CONTENT_TYPE]}"
        )

    # data (dict) and file (bytearray) have the necessary information to compose the email
    email_settings: SMTPSettings = get_email_settings(request.app)
    support_email_address = email_settings.SMTP_SENDER
    is_real_usage = any(
        env in os.environ.get("SWARM_STACK_NAME", "")
        for env in ("production", "staging")
    )

    # TODO: remove this dependency and use db instead
    db: AsyncpgStorage = get_plugin_storage(request.app)
    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    user_email = user.get("email")
    if not is_real_usage:
        support_email_address = user_email

    try:
        # NOTE: temporarily internal import to avoid render_and_send_mail to be interpreted as handler
        # TODO: Move outside when get_handlers_from_namespace is fixed
        from .login.utils_email import render_and_send_mail

        attachments = [("metadata.json", json.dumps(data, indent=4))]
        if filedata:
            attachments.append((filename, filedata))
        # send email
        await render_and_send_mail(
            request,
            to=support_email_address,
            template=themed("templates/common", EMAIL_TEMPLATE_NAME),
            context={
                "user": user_email,
                "data": json2html.convert(
                    json=json.dumps(data), table_attributes='class="pure-table"'
                ),
                "subject": "TEST: " * (not is_real_usage) + "New service submission",
            },
            attachments=attachments,
        )
    except Exception as exc:
        log.exception("Error while sending the 'new service submission' mail.")
        raise web.HTTPServiceUnavailable() from exc

    raise web.HTTPNoContent(content_type="application/json")
