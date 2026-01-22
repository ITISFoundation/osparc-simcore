from dataclasses import dataclass


@dataclass(frozen=True)
class EmailAddress:
    display_name: str
    email: str
