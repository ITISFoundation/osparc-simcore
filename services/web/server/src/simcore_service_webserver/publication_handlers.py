from aiohttp import MultipartReader, hdrs, web

from .login.decorators import RQT_USERID_KEY, login_required


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
            continue
        raise web.HTTPUnsupportedMediaType(reason=f'One part had an unexpected type: {part.headers[hdrs.CONTENT_TYPE]}')
    # data (dict) and file (bytearray) have the necessary information to compose the email
    print(data, filedata)
    user_id = request.get(RQT_USERID_KEY, -1)
    try:
        from .login.utils import (render_and_send_mail, common_themed)
        await render_and_send_mail(
            request,
            'support@osparc.io',
            common_themed('service_submission.html'),
            {
                'user': user_id,
                'json': data
            },
            filedata
        )
    except Exception:
        raise web.HTTPServiceUnavailable()

    return True
