from fastapi import FastAPI
from models_library.rpc.notifications.template import NotificationsTemplateRpcGet
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def search_templates(app: FastAPI, *, channel: str, template_name: str) -> list[NotificationsTemplateRpcGet]:
    raise NotImplementedError
