from typing import Optional

from pydantic import ByteSize


def byte_size_ids(val) -> Optional[str]:
    if isinstance(val, ByteSize):
        return val.human_readable()
    return None
