from typing import NotRequired, TypedDict


class LogExtra(TypedDict):
    log_uid: NotRequired[str]
    log_oec: NotRequired[str]


def get_log_record_extra(
    *,
    user_id: int | str | None = None,
    error_code: str | None = None,
) -> LogExtra | None:
    extra: LogExtra = {}

    if user_id:
        assert int(user_id) > 0  # nosec
        extra["log_uid"] = f"{user_id}"
    if error_code:
        extra["log_oec"] = error_code

    return extra or None
