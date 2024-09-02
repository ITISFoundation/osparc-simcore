from pydantic import EmailStr, validate_email


class LowerCaseEmailStr(EmailStr):
    @classmethod
    def validate(cls, value: EmailStr) -> EmailStr:
        email = validate_email(value)[1]
        return email.lower()
