import logging
from abc import ABC, abstractmethod

from models_library.api_schemas_webserver.wallets import (
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.users import UserID

_logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    @abstractmethod
    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentTransaction,
    ):
        ...

    @abstractmethod
    async def notify_payment_method_acked(
        self,
        user_id: UserID,
        payment_method: PaymentMethodTransaction,
    ):
        ...

    @classmethod
    def get_name(cls):
        return cls.__name__
