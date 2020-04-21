import json
import os

from aiohttp import MultipartReader, hdrs, web

from .login.decorators import RQT_USEREMAIL_KEY, login_required


@login_required
async def service_submission(request: web.Request):
    reader = MultipartReader.from_response(request)
    data = None
    filedata = None
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.headers[hdrs.CONTENT_TYPE] == 'application/json':
            data = await part.json()
            continue
        if part.headers[hdrs.CONTENT_TYPE] == 'application/zip':
            filedata = await part.read(decode=True)
            maxsize = 10 * 1024 * 1024 # 10MB
            actualsize = len(filedata)
            if actualsize > maxsize:
                raise web.HTTPRequestEntityTooLarge(maxsize, actualsize)
            filename = part.filename
            continue
        raise web.HTTPUnsupportedMediaType(reason=f'One part had an unexpected type: {part.headers[hdrs.CONTENT_TYPE]}')
    # data (dict) and file (bytearray) have the necessary information to compose the email
    user_email = request.get(RQT_USEREMAIL_KEY, -1)
    try:
        from .login.utils import (render_and_send_mail, common_themed)
        from json2html import json2html
        subject = 'New service submission'
        await render_and_send_mail(
            request,
            'pascual@itis.swiss',
            common_themed('service_submission.html'),
            {
                'user': user_email,
                'data': json2html.convert(json=json.dumps(data), table_attributes='class="pure-table"'),
                'subject': subject if 'production' in os.environ.get("SWARM_STACK_NAME") else 'TEST: ' + subject
            },
            [(filename, filedata)]
        )
    except Exception:
        raise web.HTTPServiceUnavailable()

    return True
