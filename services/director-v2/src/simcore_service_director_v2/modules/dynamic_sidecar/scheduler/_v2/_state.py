from typing import Any, Callable, Optional

from pydantic import BaseModel, Field, validator

from ._models import StateName


class State(BaseModel):
    """
    A sequence of events (functions)
    """

    name: StateName
    events: list[Callable] = Field(
        ...,
        description=(
            "list awaitables marked as events, the order in this list "
            "is the order in which events will be executed"
        ),
    )

    next_state: Optional[StateName] = Field(
        ...,
        description="optional, name of the state to run after this state",
    )
    on_error_state: Optional[StateName] = Field(
        ...,
        description="optional, name of the state to run after this state raises an unexpected error",
    )

    @property
    def events_names(self) -> list[str]:
        return [x.__name__ for x in self.events]

    @validator("events")
    @classmethod
    def ensure_all_marked_as_event(cls, events):
        for event in events:
            for attr_name in ("input_types", "return_type"):
                if not hasattr(event, attr_name):
                    raise ValueError(
                        f"Event handler {event.__name__} should expose `{attr_name}` "
                        "attribute. Was it decorated with @mark_event?"
                    )
            if type(getattr(event, "input_types")) != dict:
                raise ValueError(
                    f"`{event.__name__}.input_types` should be of type {dict}"
                )
            if getattr(event, "return_type") != dict[str, Any]:
                raise ValueError(
                    f"`{event.__name__}.return_type` should be of type {dict[str, Any]}"
                )
        return events


class StateRegistry:
    """Keeps track of state information associated to each state's name"""

    def __init__(self, *states: State) -> None:
        self._registry: dict[StateName, State] = {x.name: x for x in states}

    def __contains__(self, item: StateName) -> bool:
        return item in self._registry

    def __getitem__(self, key: StateName) -> State:
        return self._registry[key]
