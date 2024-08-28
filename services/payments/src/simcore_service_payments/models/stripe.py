from pydantic.v1 import BaseModel, HttpUrl


class InvoiceData(BaseModel):
    hosted_invoice_url: HttpUrl
