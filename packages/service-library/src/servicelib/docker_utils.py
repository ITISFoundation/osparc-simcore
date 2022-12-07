from datetime import datetime

_DOCKER_TIMESTAMP_LENGTH = len("2020-10-09T12:28:14.771034")


def to_datetime(docker_timestamp: str) -> datetime:
    # datetime_str is typically '2020-10-09T12:28:14.771034099Z'
    #  - The T separates the date portion from the time-of-day portion
    #  - The Z on the end means UTC, that is, an offset-from-UTC
    # The 099 before the Z is not clear, therefore we will truncate the last part
    # NOTE: must be in UNIX Timestamp format
    return datetime.strptime(
        docker_timestamp[:_DOCKER_TIMESTAMP_LENGTH], "%Y-%m-%dT%H:%M:%S.%f"
    )
