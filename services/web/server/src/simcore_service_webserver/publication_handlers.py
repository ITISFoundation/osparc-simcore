from aiohttp import MultipartReader, hdrs, web

from .login.decorators import login_required


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
        elif part.headers[hdrs.CONTENT_TYPE] == 'application/zip':
            filedata = await part.read(decode=True)
            continue
        else:
            raise web.HTTPUnsupportedMediaType(reason=f'One part had an unexpected type: {part.headers[hdrs.CONTENT_TYPE]}')
    # data (dict) and file (bytearray) have the necessary information to compose the email
    return True
