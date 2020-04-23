import json
import logging
import os

from aiohttp import MultipartReader, hdrs, web
from aiohttp_session import get_session
from json2html import json2html
from servicelib.application_keys import APP_CONFIG_KEY

from .login.decorators import login_required

log = logging.getLogger(__name__)

email_template_name = 'service_submission.html'

is_real_usage = any([env in os.environ.get("SWARM_STACK_NAME") for env in ('production', 'staging')])

@login_required
async def service_submission(request: web.Request):
    reader = MultipartReader.from_response(request)
    data = None
    filedata = None
    # Read multipart email
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.headers[hdrs.CONTENT_TYPE] == 'application/json':
            data = await part.json()
            continue
        if part.headers[hdrs.CONTENT_TYPE] == 'application/zip':
            filedata = await part.read(decode=True)
            # Validate max file size
            maxsize = 10 * 1024 * 1024 # 10MB
            actualsize = len(filedata)
            if actualsize > maxsize:
                raise web.HTTPRequestEntityTooLarge(maxsize, actualsize)
            filename = part.filename
            continue
        raise web.HTTPUnsupportedMediaType(reason=f'One part had an unexpected type: {part.headers[hdrs.CONTENT_TYPE]}')
    # data (dict) and file (bytearray) have the necessary information to compose the email
    session = await get_session(request)
    user_email = session.get('user')['email']
    support_email_address = request.app[APP_CONFIG_KEY]['smtp']['sender']
    try:
        from .login.utils import common_themed, render_and_send_mail
        # send email
        subject = 'New service submission'
        await render_and_send_mail(
            request,
            support_email_address if is_real_usage else user_email,
            common_themed(email_template_name),
            {
                'user': user_email,
                'data': json2html.convert(json=json.dumps(data), table_attributes='class="pure-table"'),
                'subject': subject if is_real_usage else 'TEST: ' + subject
            },
            [(filename, filedata)] if filedata else None
        )
    except Exception:
        log.exception("Error while sending the 'new service submission' mail.")
        raise web.HTTPServiceUnavailable()

    raise web.HTTPNoContent(content_type="application/json")
