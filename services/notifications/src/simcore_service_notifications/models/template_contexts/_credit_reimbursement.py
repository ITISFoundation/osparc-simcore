"""Context model for the 'credit_reimbursement' email template."""

from decimal import Decimal

from models_library.notifications import Channel
from models_library.services_types import ServiceRunID

from ..template import BaseTemplateContext, register_template_context


@register_template_context(channel=Channel.email, template_name="credit_reimbursement")
class CreditReimbursementTemplateContext(BaseTemplateContext):
    service_run_id: ServiceRunID
    reimbursed_credits: Decimal
