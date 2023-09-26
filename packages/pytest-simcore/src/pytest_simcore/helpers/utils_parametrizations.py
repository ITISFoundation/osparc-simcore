from pydantic import ByteSize


def byte_size_ids(val) -> str | None:
    if isinstance(val, ByteSize):
        return val.human_readable()
    return None
