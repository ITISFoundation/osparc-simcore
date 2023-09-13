import enum

import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata


@enum.unique
class InitPromptAckFlowState(str, enum.Enum):
    PENDING = "PENDING"  # initiated
    SUCCESS = "SUCCESS"  # completed (ack) with success
    FAILED = "FAILED"  # failed
    CANCELED = "CANCELED"  # explicitly aborted by user


#
# NOTE:
#  - This table was designed to work in an isolated database. For that reason
#    we do not use ForeignKeys to establish relations with other tables (e.g. user_id).
#  - Payment methods are owned by a user and associated to a wallet. When the same CC is added
#    in the framework by different users, the gateway will produce  different payment_method_id for each
#    of them (VERIFY assumption)
#  - A payment method is unique, i.e. only one per wallet and user. For the moment, we intentially avoid the
#    possibility of associating a payment method to more than one wallet to avoid complexity
#
payments_methods = sa.Table(
    "payments_methods",
    metadata,
    sa.Column(
        "payment_method_id",
        sa.String,
        nullable=False,
        primary_key=True,
        doc="Unique identifier of the payment method provided by payment gateway",
    ),
    sa.Column(
        "user_id",
        sa.BigInteger,
        nullable=False,
        doc="Unique identifier of the user",
        index=True,
    ),
    sa.Column(
        "wallet_id",
        sa.BigInteger,
        nullable=False,
        doc="Unique identifier to the wallet owned by the user",
        index=True,
    ),
    #
    # States of Init-Prompt-Ack flow
    #
    sa.Column(
        "initiated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        doc="Timestamps init step of the flow",
    ),
    sa.Column(
        "completed_at",
        sa.DateTime(timezone=True),
        nullable=True,
        doc="Timestamps ack step of the flow",
    ),
    sa.Column(
        "state",
        sa.Enum(InitPromptAckFlowState),
        nullable=False,
        default=InitPromptAckFlowState.PENDING,
        doc="Current state of this row in the flow ",
    ),
    sa.Column(
        "state_message",
        sa.Text,
        nullable=True,
        doc="State message to with details on the state e.g. failure messages",
    ),
    # time-stamps
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)


register_modified_datetime_auto_update_trigger(payments_methods)
