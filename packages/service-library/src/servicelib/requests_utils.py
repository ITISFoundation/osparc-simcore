from aiohttp import web


def get_request(*args, **kwargs) -> web.BaseRequest:
    """ Helper for handler function decorators to retrieve requests

    """
    request = kwargs.get('request', args[-1] if args else None)
    if not isinstance(request, web.BaseRequest):
        msg = ("Incorrect decorator usage. "
               "Expecting `def handler(request)` "
               "or `def handler(self, request)`.")
        raise RuntimeError(msg)
    return request
