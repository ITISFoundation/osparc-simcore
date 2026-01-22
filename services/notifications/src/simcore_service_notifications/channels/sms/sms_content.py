from dataclasses import dataclass


@dataclass(frozen=True)
# NOTE: SMS content model is kept for future use
class SMSNotificationContent:
    text: str
