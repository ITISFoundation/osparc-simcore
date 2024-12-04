from pydantic import BaseModel


class ComputationStart(BaseModel):
    force_restart: bool = False
    subgraph: set[str] = set()


__all__: tuple[str, ...] = ("ComputationStart",)
