import asyncio
import logging

from aiohttp import web

from simcore_service_director import config, exceptions, registry_proxy
from simcore_service_director.config import APP_REGISTRY_CACHE_DATA_KEY
from servicelib.utils import logged_gather

_logger = logging.getLogger(__name__)

TASK_NAME: str = __name__ + "_registry_caching_task"


async def registry_caching_task(app: web.Application) -> None:
    try:
        _logger.info("%s: initializing cache...", TASK_NAME)
        app[APP_REGISTRY_CACHE_DATA_KEY].clear()
        await registry_proxy.list_services(app, registry_proxy.ServiceType.ALL)
        _logger.info("%s: initialisation completed", TASK_NAME)
        while True:
            _logger.info("%s: waking up, refreshing cache...", TASK_NAME)
            try:
                keys = []
                refresh_tasks = []
                for key in app[APP_REGISTRY_CACHE_DATA_KEY]:
                    path, method = key.split(":")
                    _logger.debug("refresh %s:%s", method, path)
                    refresh_tasks.append(
                        registry_proxy.registry_request(
                            app, path, method, no_cache=True
                        )
                    )
                keys = list(app[APP_REGISTRY_CACHE_DATA_KEY].keys())
                results = await logged_gather(*refresh_tasks)

                for key, result in zip(keys, results):
                    app[APP_REGISTRY_CACHE_DATA_KEY][key] = result

            except exceptions.DirectorException:
                # if the registry is temporarily not available this might happen
                _logger.exception(
                    "%s: exception while refreshing cache, clean cache...", TASK_NAME
                )
                app[APP_REGISTRY_CACHE_DATA_KEY].clear()

            _logger.info(
                "cache refreshed %s: sleeping for %ss...",
                TASK_NAME,
                config.DIRECTOR_REGISTRY_CACHING_TTL,
            )
            await asyncio.sleep(config.DIRECTOR_REGISTRY_CACHING_TTL)
    except asyncio.CancelledError:
        _logger.info("%s: cancelling task...", TASK_NAME)
    except Exception:  # pylint: disable=broad-except
        _logger.exception("%s: Unhandled exception while refreshing cache", TASK_NAME)
    finally:
        _logger.info("%s: finished task...clearing cache...", TASK_NAME)
        app[APP_REGISTRY_CACHE_DATA_KEY].clear()


async def setup_registry_caching_task(app: web.Application) -> None:
    app[APP_REGISTRY_CACHE_DATA_KEY] = {}
    app[TASK_NAME] = asyncio.get_event_loop().create_task(registry_caching_task(app))

    yield

    task = app[TASK_NAME]
    task.cancel()
    await task


def setup(app: web.Application) -> None:
    if config.DIRECTOR_REGISTRY_CACHING:
        app.cleanup_ctx.append(setup_registry_caching_task)


__all__ = ["setup", "APP_REGISTRY_CACHE_DATA_KEY"]
