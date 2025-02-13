import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER


def version(column_or_value):
    # converts version value string to array[integer] that can be compared
    return sa.func.string_to_array(column_or_value, ".").cast(ARRAY(INTEGER))
