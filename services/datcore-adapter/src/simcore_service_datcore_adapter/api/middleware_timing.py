import time
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.debug("time to process %.2fs", process_time)
    response.headers["X-Process-Time"] = str(process_time)
    return response
