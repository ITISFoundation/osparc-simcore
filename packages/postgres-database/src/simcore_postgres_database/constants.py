from decimal import Decimal
from typing import Final

# NOTE: this is sync with DECIMAL_PLACES@ packages/models-library/src/models_library/basic_types.py using test_postgres_and_models_library_same_decimal_places_constant
DECIMAL_PLACES: Final = 2

# NOTE: Constant used in the exp argument of quantize to convert decimals as: Decimal().quantize(QUANTIZE_EXP_ARG)
# See https://docs.python.org/3/library/decimal.html#decimal.Decimal.quantize
QUANTIZE_EXP_ARG: Final = Decimal(f"1e-{DECIMAL_PLACES}")

# sqlalchemy dialects used to open postgres connections. They are spelled out, and declared here,
# because the same urls get built in the fixtures of every service and a driver change upstream
# must not silently move them.
#
# psycopg (3) is the successor of psycopg2 and the dialect sqlalchemy selects for a bare
# 'postgresql://' url since sqlalchemy 2.1. The sync engines use it.
POSTGRES_SYNC_DSN_SCHEME: Final = "postgresql+psycopg"

# the dialect of the async engines, i.e. those created with sqlalchemy.ext.asyncio
POSTGRES_ASYNC_DSN_SCHEME: Final = "postgresql+asyncpg"
