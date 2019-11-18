from aiohttp import web

async def mark_service_for_deletion(service_uuid: str, app: web.Application):
    pass

async def mark_all_user_services_for_deletion(user_id: str, app: web.Application):
    pass

async def mark_all_project_services_for_deletion(project_id: str, app: web.Application):
    pass

async def recover_service_from_deletion(service_uuid: str, app: web.Application):
    pass