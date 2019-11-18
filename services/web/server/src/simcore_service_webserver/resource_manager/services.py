import logging

from aiohttp import web

from ..signals import SignalType, observe

log = logging.getLogger(__name__)

async def mark_service_for_deletion(service_uuid: str, app: web.Application):
    pass

@observe(event=SignalType.SIGNAL_USER_DISCONNECT)
async def mark_all_user_services_for_deletion(user_id: str, app: web.Application):
    log.info("marking services of user %s for deletion...", user_id)


async def mark_all_project_services_for_deletion(project_id: str, app: web.Application):
    log.info("marking services of project %s for deletion...", project_id)

async def recover_service_from_deletion(service_uuid: str, app: web.Application):
    pass
