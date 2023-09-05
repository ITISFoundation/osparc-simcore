#
# upon payment completion:
#
#  - TOP up credits: send to RUT
#  - pub/sub ack messages -> webserver will consume and notify front-end
#


async def top_up_credits():
    raise NotImplementedError


async def notify_payment_transaction_completed():
    raise NotImplementedError
