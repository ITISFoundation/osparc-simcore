from pydantic import EmailStr


class LowerCaseEmailStr(EmailStr):
    @classmethod
    def validate(cls, value: str) -> str:
        return super().validate(value).lower()
