from jinja2 import Environment
from notifications_library._models import ProductData, UserData
from notifications_library._render import create_default_env, render_email_parts
from notifications_library.payments import ON_PAYED_EVENT_EMAIL_TEMPLATES, PaymentData


def test_on_payed_event(
    user_data: UserData,
    product_data: ProductData,
    payment_data: PaymentData,
):
    # consolidate templates for product

    # build env that contains emplates
    templates = ON_PAYED_EVENT_EMAIL_TEMPLATES

    env: Environment = create_default_env()
    parts = render_email_parts(
        env,
        "on_payed",
        user=user_data,
        product=product_data,
        payment=payment_data,
    )

    print(parts)
    print(parts.suject)
    print(parts.text_content)
