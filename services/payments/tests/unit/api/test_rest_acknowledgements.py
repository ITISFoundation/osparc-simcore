import httpx
from faker import Faker
from fastapi import status
from simcore_service_payments.models.schemas.acknowledgements import AckPayment


async def test_login_complete_payment(
    client: httpx.AsyncClient, faker: Faker, auth_headers: dict[str, str]
):
    payments_id = faker.uuid4()
    payment_ack = AckPayment(success=True, invoice_url=faker.url()).dict()

    # w/o header
    response = await client.post(
        f"/v1/payments/{payments_id}:ack",
        json=payment_ack,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    # w/ header
    response = await client.post(
        f"/v1/payments/{payments_id}:ack", json=payment_ack, headers=auth_headers
    )
    # NOTE: for the moment this entry is not implemented
    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED, response.text
