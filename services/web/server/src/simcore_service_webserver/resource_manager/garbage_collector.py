"""The garbage collector runs as an aiohttp background task at pre-defined interval until the aiohttp app is closed.

    Its tasks are to collect resources that are no longer "alive".
    The tasks are defined as alive when the registry alive key is no longer available (see (registry.py)),
    thus the corresponding key is deamed as dead, and so are its attached resources if any.
    The garbage collector shall then close/delete these resources.
"""

import asyncio
import logging

from aiohttp import web

from servicelib.observer import emit
from servicelib.utils import logged_gather

from .config import APP_GARBAGE_COLLECTOR_KEY, get_garbage_collector_interval
from .registry import RedisResourceRegistry, get_registry

logger = logging.getLogger(__name__)


async def collect_garbage(registry: RedisResourceRegistry, app: web.Application):
    logger.info("collecting garbage...")
    alive_keys, dead_keys = await registry.get_all_resource_keys()
    logger.debug("potential dead keys: %s", dead_keys)

    # check if we find potential stuff to close
    for key in dead_keys:
        resources = await registry.get_resources(key)
        if not resources:
            # no resource, remove the key then
            await registry.remove_key(key)
            continue
        logger.debug("found the following resources: %s", resources)
        # find if there are alive entries using these resources
        for resource_name, resource_value in resources.items():
            other_keys = [
                x
                for x in await registry.find_keys((resource_name, resource_value))
                if x != key
            ]
            # the resource ref can be closed anyway
            logger.debug("removing resource entry: %s: %s", key, resources)
            await registry.remove_resource(key, resource_name)

            # check if the resource is still in use in the alive keys
            if not any(elem in alive_keys for elem in other_keys):
                # remove the resource from the other keys as well
                remove_tasks = [
                    registry.remove_resource(x, resource_name) for x in other_keys
                ]
                if remove_tasks:
                    logger.debug(
                        "removing resource entry: %s: %s", other_keys, resources
                    )
                    await logged_gather(*remove_tasks, reraise=False)

                logger.debug(
                    "the resources %s:%s of %s may be now safely closed",
                    resource_name,
                    resource_value,
                    key,
                )
                await emit(
                    event="SIGNAL_PROJECT_CLOSE",
                    user_id=None,
                    project_uuid=resource_value,
                    app=app,
                )


async def garbage_collector_task(app: web.Application):
    logger.info("Starting garbage collector...")
    try:
        registry = get_registry(app)
        interval = get_garbage_collector_interval(app)
        while True:
            await collect_garbage(registry, app)
            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        pass
    finally:
        pass


async def setup_garbage_collector_task(app: web.Application):
    app[APP_GARBAGE_COLLECTOR_KEY] = asyncio.get_event_loop().create_task(
        garbage_collector_task(app)
    )
    yield
    task = app[APP_GARBAGE_COLLECTOR_KEY]
    task.cancel()
    await task


def setup(app: web.Application):
    app.cleanup_ctx.append(setup_garbage_collector_task)
