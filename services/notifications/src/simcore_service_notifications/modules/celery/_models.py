from typing import Annotated

from pydantic import Field, StringConstraints
from servicelib.celery.models import OwnerMetadata

from ..._meta import APP_NAME


class NotificationsOwnerMetadata(OwnerMetadata):
    owner: Annotated[str, StringConstraints(pattern=rf"^{APP_NAME}$"), Field(frozen=True)] = APP_NAME
