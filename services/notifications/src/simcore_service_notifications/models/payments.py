from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentData:
    price_dollars: str
    osparc_credits: str
    invoice_url: str
    invoice_pdf_url: str
