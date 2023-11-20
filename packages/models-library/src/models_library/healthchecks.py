#
# healthcheck models for liveness probes and readiness probes
#
# SEE https://medium.com/polarsquad/how-should-i-answer-a-health-check-aa1fcf6e858e
# SEE https://docs.docker.com/engine/reference/builder/#healthcheck


from datetime import timedelta
from typing import TypeAlias

from pydantic import BaseModel


class IsResponsive(BaseModel):
    elapsed: timedelta  # time elapsed to respond

    def __bool__(self) -> bool:
        return True


class IsNonResponsive(BaseModel):
    reason: str

    def __bool__(self) -> bool:
        return False


LivenessResult: TypeAlias = IsResponsive | IsNonResponsive
