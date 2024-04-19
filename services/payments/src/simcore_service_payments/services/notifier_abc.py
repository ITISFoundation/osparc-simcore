import logging
from abc import ABC, abstractmethod

from models_library.api_schemas_webserver.wallets import PaymentMethodTransaction
from models_library.users import UserID

from ..models.db import PaymentsTransactionsDB

_logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    @abstractmethod
    async def notify_payment_completed(
        self,
        user_id: UserID,
        payment: PaymentsTransactionsDB,
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
