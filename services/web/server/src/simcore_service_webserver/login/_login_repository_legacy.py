from datetime import datetime
from logging import getLogger
from typing import Literal, TypedDict

_logger = getLogger(__name__)


## MODELS

ActionLiteralStr = Literal[
    "REGISTRATION", "INVITATION", "RESET_PASSWORD", "CHANGE_EMAIL"
]


class BaseConfirmationTokenDict(TypedDict):
    code: str
    action: ActionLiteralStr


class ConfirmationTokenDict(BaseConfirmationTokenDict):
    # SEE packages/postgres-database/src/simcore_postgres_database/models/confirmations.py
    user_id: int
    created_at: datetime
    # SEE handlers_confirmation.py::email_confirmation to determine what type is associated to each action
    data: str | None
