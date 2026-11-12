"""Tests for the broker log attribution that parallel runs rely on

The lines are verbatim from a RabbitMQ 4.1.6 container where two clients raised a channel error,
one on vhost `pytest_gw0` as user `pytest_gw0` and one on `/` as `guest`, plus a rejected login
and the `rebuilding indices from scratch` notice.
"""

import pytest
from pytest_simcore.helpers.rabbitmq_logs import attribute_log_lines

CHANNEL_ERROR_GUEST = (
    "2026-11-10 11:29:35.388581+00:00 [error] <0.819.0> Channel error on connection <0.809.0> "
    "(172.17.0.1:53266 -> 172.17.0.2:5672, vhost: '/', user: 'guest'), channel 1:"
)
CHANNEL_ERROR_GW0 = (
    "2026-11-10 11:29:35.397263+00:00 [error] <0.835.0> Channel error on connection <0.826.0> "
    "(172.17.0.1:53276 -> 172.17.0.2:5672, vhost: 'pytest_gw0', user: 'pytest_gw0'), channel 1:"
)
PRECONDITION_FAILED = (
    "2026-11-10 11:29:35.397263+00:00 [error] <0.835.0> operation exchange.declare caused a channel "
    "exception precondition_failed: unknown exchange type 'x-not-a-type'"
)
PRECONDITION_FAILED_GUEST = PRECONDITION_FAILED.replace("<0.835.0>", "<0.819.0>").replace("35.397263", "35.388581")
CONNECTION_STARTING = (
    "2026-11-10 11:29:35.402994+00:00 [error] <0.842.0> Error on AMQP connection <0.842.0> "
    "(172.17.0.1:53278 -> 172.17.0.2:5672, state: starting):"
)
LOGIN_REFUSED = (
    "2026-11-10 11:29:35.402994+00:00 [error] <0.842.0> PLAIN login refused: user 'nope' - invalid credentials"
)
CLOSING_GUEST = (
    "2026-11-10 11:29:38.424781+00:00 [warning] <0.809.0> closing AMQP connection <0.809.0> "
    "(172.17.0.1:53266 -> 172.17.0.2:5672 - client_master, vhost: '/', user: 'guest', duration: '3s'):"
)
CLOSING_GW0 = (
    "2026-11-10 11:29:38.425130+00:00 [warning] <0.826.0> closing AMQP connection <0.826.0> "
    "(172.17.0.1:53276 -> 172.17.0.2:5672 - client_gw0, vhost: 'pytest_gw0', user: 'pytest_gw0', "
    "duration: '3s'):"
)
CLIENT_CLOSED = "2026-11-10 11:29:38.425130+00:00 [warning] <0.826.0> client unexpectedly closed TCP connection"
REBUILDING_INDICES = (
    "2026-11-10 11:29:35.327959+00:00 [warning] <0.769.0> Message store "
    '"5XFSIKCZT2J1G9I123PYVZ5JN/msg_store_persistent": rebuilding indices from scratch'
)

BROKER_LOG = [
    REBUILDING_INDICES,
    CHANNEL_ERROR_GUEST,
    PRECONDITION_FAILED_GUEST,
    CHANNEL_ERROR_GW0,
    PRECONDITION_FAILED,
    CONNECTION_STARTING,
    LOGIN_REFUSED,
    CLOSING_GUEST,
    CLOSING_GW0,
    CLIENT_CLOSED,
]


def _buckets(worker_id: str = "gw0"):
    attribution = attribute_log_lines(BROKER_LOG, worker_user=f"pytest_{worker_id}", worker_vhost=f"pytest_{worker_id}")
    return attribution.mine, attribution.others, attribution.unattributed


def test_a_continuation_line_keeps_the_entry_it_belongs_to():
    mine, others, _ = _buckets()

    assert CHANNEL_ERROR_GW0 in mine
    # the line continuing a channel error names no principal, only the same reporting pid
    assert PRECONDITION_FAILED in mine
    assert CLIENT_CLOSED in mine
    assert PRECONDITION_FAILED_GUEST in others


def test_another_workers_traffic_is_not_mine():
    mine, others, _ = _buckets()

    assert {CHANNEL_ERROR_GUEST, CLOSING_GUEST, PRECONDITION_FAILED_GUEST} <= set(others)
    assert not set(mine) & set(others)


def test_a_line_naming_this_vhost_and_another_user_is_not_mine():
    """a health check looking into this worker's vhost must not fail the test it runs in"""
    attribution = attribute_log_lines(
        [
            (
                "2026-11-10 11:29:35.000000+00:00 [warning] <0.900.0> closing AMQP connection <0.900.0> "
                "(172.17.0.1:1 -> 172.17.0.2:5672, vhost: 'pytest_gw0', user: 'simcore', duration: '1s'):"
            )
        ],
        worker_user="pytest_gw0",
        worker_vhost="pytest_gw0",
    )

    assert not attribution.mine
    assert len(attribution.others) == 1


def test_a_rejected_login_is_attributed_to_the_user_it_names():
    mine = attribute_log_lines([LOGIN_REFUSED], worker_user="nope", worker_vhost="pytest_gw1")
    other = attribute_log_lines([LOGIN_REFUSED], worker_user="pytest_gw0", worker_vhost="pytest_gw0")

    assert mine.mine == [LOGIN_REFUSED]
    assert other.others == [LOGIN_REFUSED]


def test_lines_are_unattributed_when_no_principal_was_named_yet():
    _, others, unattributed = _buckets()

    # the notice names no connection at all, and a refused login logs its header before the broker
    # learns who was trying to log in
    assert set(unattributed) == {REBUILDING_INDICES, CONNECTION_STARTING}
    assert LOGIN_REFUSED in others


def test_a_serial_run_is_attributed_by_the_stack_principal():
    """outside xdist the run logs in as the stack's own user, and the lines naming nobody stay
    unattributed, which is why the caller fails on them when the broker is not shared"""
    attribution = attribute_log_lines(BROKER_LOG, worker_user="guest", worker_vhost="/")

    assert CHANNEL_ERROR_GUEST in attribution.mine
    assert set(attribution.mine) | set(attribution.others) | set(attribution.unattributed) == set(BROKER_LOG)
    assert set(attribution.unattributed) == {REBUILDING_INDICES, CONNECTION_STARTING}


@pytest.mark.parametrize(
    "line, expected",
    [
        ("2026-11-10 11:29:35.000000+00:00 [error] <0.1.0> names nobody", "unattributed"),
        ("2026-11-10 11:29:35.000000+00:00 [error] <0.1.0> vhost: 'pytest_gw0'", "mine"),
        ("2026-11-10 11:29:35.000000+00:00 [error] <0.1.0> user: 'pytest_gw0'", "mine"),
        ("2026-11-10 11:29:35.000000+00:00 [error] <0.1.0> vhost: 'pytest_gw1'", "others"),
    ],
)
def test_a_single_principal_is_enough(line: str, expected: str):
    attribution = attribute_log_lines([line], worker_user="pytest_gw0", worker_vhost="pytest_gw0")

    assert getattr(attribution, expected) == [line]
