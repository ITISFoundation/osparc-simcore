from pydantic import ConstrainedDecimal
from simcore_postgres_database.models.payments_transactions import DECIMAL_PLACES


class AmountDecimal(ConstrainedDecimal):
    """Use for any amount in credits or currency"""

    gt = 0
    lt = 1e6
    decimal_places = DECIMAL_PLACES
