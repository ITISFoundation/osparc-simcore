from typing import Dict, Optional

from pydantic import BaseModel, Field, constr

from models_library.constants import VERSION_RE

VersionStr = constr(regex=VERSION_RE)


class Meta(BaseModel):
    name: str
    version: VersionStr
    released: Optional[Dict[str, VersionStr]] = Field(
        None, description="Maps every route's path tag with a released version"
    )

    class Config:
        schema_extra = {
            "example": {
                "name": "simcore_service_foo",
                "version": "2.4.45",
                "released": {"v1": "1.3.4", "v2": "2.4.45"},
            }
        }
