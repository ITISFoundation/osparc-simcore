import sqlalchemy as sa
from simcore_postgres_database.models.payments_autorecharge import payments_autorecharge
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert


class Statements:
    @staticmethod
    def is_valid_payment_method(user_id, wallet_id, payment_method_id):
        return sa.select(payments_methods.c.payment_method_id).where(
            (payments_methods.c.user_id == user_id)
            & (payments_methods.c.wallet_id == wallet_id)
            & (payments_methods.c.payment_method_id == payment_method_id)
            & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
        )

    @staticmethod
    def get_wallet_autorecharge(wallet_id):
        return (
            sa.select(
                payments_autorecharge.c.id.label("payments_autorecharge_id"),
                payments_methods.c.user_id,
                payments_methods.c.wallet_id,
                payments_autorecharge.c.primary_payment_method_id,
                payments_autorecharge.c.enabled,
                payments_autorecharge.c.min_balance_in_usd,
                payments_autorecharge.c.inc_payment_amount_in_usd,
                payments_autorecharge.c.inc_payment_countdown,
            )
            .select_from(
                payments_methods.join(
                    payments_autorecharge,
                    (payments_methods.c.wallet_id == payments_autorecharge.c.wallet_id)
                    & (
                        payments_methods.c.payment_method_id
                        == payments_autorecharge.c.primary_payment_method_id
                    ),
                )
            )
            .where(
                (payments_methods.c.wallet_id == wallet_id)
                & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
            )
        )

    @staticmethod
    def upsert_wallet_autorecharge(wallet_id, ppm, th, ip, cd):
        # using this primary payment-method, create an autorecharge
        # NOTE: requires the entire
        values = {
            "wallet_id": wallet_id,
            "primary_payment_method_id": ppm,
            "min_balance_in_usd": th,
            "inc_payment_amount_in_usd": ip,
            "inc_payment_countdown": cd,
        }

        insert_stmt = pg_insert(payments_autorecharge).values(**values)
        return insert_stmt.on_conflict_do_update(
            index_elements=[payments_autorecharge.c.wallet_id],
            set_=values,
        ).returning(sa.literal_column("*"))

    @staticmethod
    def update_wallet_autorecharge(wallet_id, **values):
        return (
            payments_autorecharge.update()
            .values(**values)
            .where(payments_autorecharge.c.wallet_id == wallet_id)
            .returning(payments_autorecharge.c.id)
        )

    @staticmethod
    def decrease_wallet_autorecharge_countdown(wallet_id):
        return (
            payments_autorecharge.update()
            .where(
                (payments_autorecharge.c.wallet_id == wallet_id)
                & (payments_autorecharge.c.inc_payment_countdown is not None)
            )
            .values(
                inc_payment_countdown=payments_autorecharge.c.inc_payment_countdown - 1,
            )
            .returning(payments_autorecharge.c.inc_payment_countdown)
        )
