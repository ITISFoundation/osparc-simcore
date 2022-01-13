"""
Adds type hints to data structures in tenacity library
"""

from typing import TypedDict


class TenacityStatsDict(TypedDict, total=False):
    start_time: int
    attempt_number: int
    idle_for: int
    delay_since_first_attempt: int
