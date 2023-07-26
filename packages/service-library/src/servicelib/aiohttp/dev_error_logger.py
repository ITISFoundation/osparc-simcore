import logging
import traceback

from aiohttp.web import Application, HTTPError, Request, middleware
from servicelib.aiohttp.typing_extension import Handler, Middleware

_logger = logging.getLogger(__name__)

_SEP = "|||"


def _middleware_factory() -> Middleware:
    @middleware
    async def middleware_handler(request: Request, handler: Handler):
        try:
            return await handler(request)
        except HTTPError as err:
            fields = {
                "Body": err.body,
                "Status": err.status,
                "Reason": err.reason,
                "Headers": err.headers,
                "Traceback": "\n".join(traceback.format_tb(err.__traceback__)),
            }
            formatted_error = "".join(
                [f"\n{_SEP}{k}{_SEP}\n{v}" for k, v in fields.items()]
            )
            _logger.debug("Error serialized to client:%s", formatted_error)
            raise

    return middleware_handler  # type: ignore[no-any-return]


def setup_dev_error_logger(app: Application) -> None:
    _logger.info("Setting up dev_error_logger")
    app.middlewares.append(_middleware_factory())
