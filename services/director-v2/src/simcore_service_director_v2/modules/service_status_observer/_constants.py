from typing import Final

from pydantic import NonNegativeInt

SERVICE_CHECK_INTERVAL: Final[NonNegativeInt] = 60
CACHE_TTL: Final[NonNegativeInt] = SERVICE_CHECK_INTERVAL * 2
