import logging

from fastapi import FastAPI
from models_library.rabbitmq_messages import WalletCreditsMessage
from pydantic import parse_raw_as

_logger = logging.getLogger(__name__)


async def process_message(app: FastAPI, data: bytes) -> bool:
    assert app  # nosec
    rabbit_message = parse_raw_as(WalletCreditsMessage, data)
    _logger.debug("Process msg: %s", rabbit_message)

    # 1. Check if auto-recharge functionality is ON for wallet_id
    # 2. Check if wallet credits are bellow the threshold
    # 3. Get Payment method
    # 4. Pay with payment method

    return True
