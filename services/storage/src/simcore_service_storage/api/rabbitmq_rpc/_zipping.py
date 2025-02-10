from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def start_zipping(paths: list[str]) -> str:
    return f"Started zipping [ { ','.join(paths) } ]"
