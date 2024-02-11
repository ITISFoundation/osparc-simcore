from aiohttp import web
from servicelib.aiohttp.exception_handlers import (
    add_exception_handler,
    add_exception_mapper,
    handle_registered_exceptions,
    setup_exception_handlers,
)


def test_it():
    class MyException(Exception):
        ...

    class OtherException(Exception):
        ...

    app = web.Application()

    async def my_error_handler(request: web.Request, exc: MyException):
        return web.HTTPNotFound()

    # define at the app level
    setup_exception_handlers(app)
    add_exception_handler(app, MyException, my_error_handler)
    add_exception_mapper(app, OtherException, web.HTTPNotFound)

    async def foo():
        raise MyException

    routes = web.RouteTableDef()

    @routes.get("/home")
    @handle_registered_exceptions()
    async def home(_request: web.Request):
        await foo()
        return web.HTTPOk()
