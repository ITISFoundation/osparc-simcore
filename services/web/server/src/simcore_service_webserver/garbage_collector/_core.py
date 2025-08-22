"""Core implementation of garbage collector"""

import logging

from aiohttp import web
from servicelib.logging_utils import log_catch, log_context

from ..resource_manager.registry import get_registry
from ._core_disconnected import remove_disconnected_user_resources
from ._core_guests import remove_users_manually_marked_as_guests
from ._core_orphans import remove_orphaned_services

_logger = logging.getLogger(__name__)


async def collect_garbage(app: web.Application):
    """
    Garbage collection has the task of removing trash (i.e. unused resources) from the system. The trash
    can be divided in:

    - Websockets & Redis (used to keep track of current active connections)
    - GUEST users (used for temporary access to the system which are created on the fly)
    - Deletion of users. If a user needs to be deleted it can be set as GUEST in the database

    The resources are Redis entries where all information regarding all the
    websocket identifiers for all opened tabs accross all browser for each user
    are stored.

    The alive/dead keys are normal Redis keys. To each key an ALIVE key is associated,
    which has an assigned TTL (Time To Live). The browser will call the `client_heartbeat` websocket
    endpoint to refresh the TTL, thus declaring that the user (websocket connection) is
    still active. The `resource_deletion_timeout_seconds` is the TTL of the key.

    The field `garbage_collection_interval_seconds` defines the interval at which this
    function will be called.
    """
    registry = get_registry(app)

    with (
        log_catch(_logger, reraise=False),
        log_context(
            _logger, logging.INFO, "Step 1: Removes disconnected user sessions"
        ),
    ):
        # Triggers signal to close possible pending opened projects
        # Removes disconnected GUEST users after they finished their sessions
        await remove_disconnected_user_resources(registry, app)

    with (
        log_catch(_logger, reraise=False),
        log_context(
            _logger, logging.INFO, "Step 2: Removes users manually marked for removal"
        ),
    ):
        # if a user was manually marked as GUEST it needs to be
        # removed together with all the associated projects
        await remove_users_manually_marked_as_guests(registry, app)

    with (
        log_catch(_logger, reraise=False),
        log_context(_logger, logging.INFO, "Step 3: Removes orphaned services"),
    ):
        # For various reasons, some services remain pending after
        # the projects are closed or the user was disconencted.
        # This will close and remove all these services from
        # the cluster, thus freeing important resources.
        await remove_orphaned_services(registry, app)
