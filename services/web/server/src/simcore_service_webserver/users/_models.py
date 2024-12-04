from pydantic import BaseModel


#
# REST models
#
class ProfilePrivacyGet(BaseModel):
    hide_fullname: bool
    hide_email: bool


class ProfilePrivacyUpdate(BaseModel):
    hide_fullname: bool | None = None
    hide_email: bool | None = None
