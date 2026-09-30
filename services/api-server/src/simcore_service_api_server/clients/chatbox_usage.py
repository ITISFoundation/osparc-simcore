"""Chatbox Usage Ledger: Redis-backed enforcement of Chatbox usage limits (ADR-0001).

The whole Usage Ledger lives in the platform cache Redis on a dedicated database:
- window hash   api-server:chatbox:usage:window:{user_id}:{product_name}
    fields spend / reservations (USD); TTL = the fixed Usage Window, started at the
    holder's first admitted request (the TTL is the exact "available again at" answer)
- global hash   api-server:chatbox:usage:global
    fields spend / reservations (USD) and requests — cumulative vs the Provider Budget
- rate key      api-server:chatbox:rate:{credential_hash}:{minute-bucket}
- ledger stream api-server:chatbox:usage:ledger — one entry per completion (Usage Ledger)

Money layers (Window Quota, Global Budget Guard) are fail-closed: a Redis failure
rejects the request with a 503. The Rate Limit is fail-open: a Redis failure lets the
request through.

Admission is a compare-and-swap against Spend + in-flight Reservations, so concurrent
requests cannot overshoot the Window Quota by more than the Reservations they hold. The
Reservation is sized from the rolling global average Spend/request (a single Redis stat)
times a safety factor; before the platform has any completed request there is no average
to size from, so the cold-start Reservation is the full Window Quota — at most one
request per window may then be in flight, which closes the cold-start overshoot.
"""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

import redis.asyncio as aioredis
import redis.exceptions
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from models_library.products import ProductName
from models_library.users import UserID
from prometheus_client import CollectorRegistry, Counter, Gauge
from pydantic import NonNegativeFloat, NonNegativeInt
from redis.exceptions import WatchError
from servicelib.logging_utils import log_catch
from servicelib.redis import RedisClientSDK
from settings_library.redis import RedisDatabase

from .._meta import PROJECT_NAME
from ..core.settings import ChatboxUsageLimitsSettings
from ..exceptions.usage_limit_errors import (
    ChatboxRateLimitedError,
    ChatboxWindowQuotaExceededError,
    ProviderBudgetExhaustedError,
    UsageLedgerUnavailableError,
)

_logger = logging.getLogger(__name__)

_METRICS_NAMESPACE: Final[str] = PROJECT_NAME.replace("-", "_")

_KEY_PREFIX: Final[str] = "api-server:chatbox"
_WINDOW_KEY_PREFIX: Final[str] = f"{_KEY_PREFIX}:usage:window"
_GLOBAL_KEY: Final[str] = f"{_KEY_PREFIX}:usage:global"
_LEDGER_STREAM_KEY: Final[str] = f"{_KEY_PREFIX}:usage:ledger"
_RATE_KEY_PREFIX: Final[str] = f"{_KEY_PREFIX}:rate"

_RATE_KEY_TTL_SECONDS: Final[NonNegativeInt] = 61
_LEDGER_STREAM_MAXLEN: Final[NonNegativeInt] = 100_000
_CAS_MAX_ATTEMPTS: Final[NonNegativeInt] = 5
_TTL_KEY_MISSING: Final[int] = -2  # Redis TTL reply when the key does not exist
_FLOAT_EPS: Final[float] = 1e-9
_CHARS_PER_TOKEN: Final[NonNegativeInt] = 4

# connection/timeout/protocol errors mean the ledger is unreachable
_REDIS_UNAVAILABLE_ERRORS: Final[tuple[type[Exception], ...]] = (redis.exceptions.RedisError, OSError)

_FIELD_SPEND: Final[str] = "spend"
_FIELD_RESERVATIONS: Final[str] = "reservations"
_FIELD_REQUESTS: Final[str] = "requests"


def _field_float(hash_: dict[str, str], field: str) -> float:
    value = float(hash_.get(field, 0) or 0)
    # a Redis flush mid-flight can leave a released Reservation subtracted from a fresh
    # counter; treat negative aggregates as zero so enforcement stays conservative
    return max(0.0, value)


def _budget_hard_stop_hit(global_stats: dict[str, str], settings: ChatboxUsageLimitsSettings) -> bool:
    """True when committed Spend (actual + in-flight Reservations) reached the hard stop.

    Counting Reservations is what bounds concurrent and per-request overshoot: a guard on
    settled Spend alone would let every in-flight completion pass unchecked.
    """
    committed = _field_float(global_stats, _FIELD_SPEND) + _field_float(global_stats, _FIELD_RESERVATIONS)
    return committed >= settings.HARD_STOP_FRACTION * settings.PROVIDER_BUDGET_USD


@dataclass(frozen=True, kw_only=True)
class UsageRecord:
    """OpenAI-style token usage of one completion (see CONTEXT.md § Spend)."""

    total_tokens: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated: bool = False

    @classmethod
    def estimated_from_text(cls, *, input_chars: int, output_chars: int) -> "UsageRecord":
        # ~4 characters per token (usual rule of thumb); used only when the Chatbox
        # response lacked usage — the request itself must never fail because of it
        return cls(total_tokens=(input_chars + output_chars) // _CHARS_PER_TOKEN, estimated=True)


@dataclass(frozen=True, kw_only=True)
class Reservation:
    """A provisional Spend placed against the Window Quota (see CONTEXT.md)."""

    user_id: UserID
    product_name: ProductName
    amount_usd: float


class _UsageMetrics:
    def __init__(self, registry: CollectorRegistry) -> None:
        self.spend_usd_total = Counter(
            "chatbox_spend_usd_total",
            "Cumulative Chatbox Spend in USD, per product",
            ["product_name"],
            namespace=_METRICS_NAMESPACE,
            registry=registry,
        )
        self.spend_usd_global_total = Counter(
            "chatbox_spend_usd_global_total",
            "Cumulative platform Chatbox Spend in USD, across all products",
            namespace=_METRICS_NAMESPACE,
            registry=registry,
        )
        self.provider_budget_fraction = Gauge(
            "chatbox_provider_budget_fraction",
            "Cumulative platform Chatbox Spend as a fraction of the Provider Budget (50/75 % alerts)",
            namespace=_METRICS_NAMESPACE,
            registry=registry,
        )
        self.released_reservations_total = Counter(
            "chatbox_released_reservations_total",
            "# Reservations refunded without reconciling to actual Spend (possible Provider Budget under-count)",
            ["reason"],
            namespace=_METRICS_NAMESPACE,
            registry=registry,
        )
        self.ledger_failures_total = Counter(
            "chatbox_usage_ledger_failures_total",
            "# Requests a layer could not enforce due to Redis failures (fail-open/fail-closed), per stage",
            ["stage"],
            namespace=_METRICS_NAMESPACE,
            registry=registry,
        )


@dataclass
class ChatboxUsageLedger:
    """All enforcement layers around the Chatbox, backed by one Redis database.

    Both request paths (direct streaming and Celery-worker completions) enforce against
    the same Redis instance.
    """

    _client: RedisClientSDK
    _settings: ChatboxUsageLimitsSettings
    _metrics: _UsageMetrics

    @property
    def _redis(self) -> aioredis.Redis:
        return self._client.redis

    def _window_key(self, user_id: UserID, product_name: ProductName) -> str:  # pylint: disable=no-self-use
        return f"{_WINDOW_KEY_PREFIX}:{user_id}:{product_name}"

    # -- Rate Limit (per API key, fail-open) ---------------------------------------

    async def acquire_rate_limit(self, credential_hash: str) -> None:
        """Rate Limit: ``REQUESTS_PER_MINUTE`` per (hash of an) API key.

        Fail-open on Redis errors: the Rate Limit is only a burst guard, the money
        layers still protect the Provider Budget.
        """
        minute_bucket = int(time.time() // 60)
        key = f"{_RATE_KEY_PREFIX}:{credential_hash}:{minute_bucket}"
        try:
            count: int = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, _RATE_KEY_TTL_SECONDS)
        except _REDIS_UNAVAILABLE_ERRORS:
            self._metrics.ledger_failures_total.labels(stage="rate_limit").inc()
            _logger.warning("Rate limit could not be checked (fail-open)", exc_info=True)
            return

        if count > self._settings.REQUESTS_PER_MINUTE:
            try:
                ttl: int = await self._redis.ttl(key)
            except _REDIS_UNAVAILABLE_ERRORS:
                # fail-open: the counter already proved the request was over the limit and
                # it stays denied, but the reset time falls back to the bucket's lifetime
                ttl = _RATE_KEY_TTL_SECONDS
            raise ChatboxRateLimitedError(
                requests_per_minute=self._settings.REQUESTS_PER_MINUTE,
                retry_after_seconds=ttl if ttl > 0 else 60,
            )

    # -- Window Quota + Global Budget Guard (fail-closed) --------------------------

    async def admit_and_reserve(self, *, user_id: UserID, product_name: ProductName) -> Reservation:
        """Atomic pre-check + Reservation placement for one completion.

        Raises:
            ProviderBudgetExhaustedError: Global Budget Guard hard stop is hit.
            ChatboxWindowQuotaExceededError: the Reservation does not fit the Window Quota.
            UsageLedgerUnavailableError: Redis cannot be trusted (fail-closed).
        """
        window_key = self._window_key(user_id, product_name)
        allowance = float(self._settings.WINDOW_SPEND_USD)

        for _ in range(_CAS_MAX_ATTEMPTS):
            try:
                async with self._redis.pipeline() as pipe:
                    await pipe.watch(window_key, _GLOBAL_KEY)
                    window = await pipe.hgetall(window_key)
                    window_ttl: int = await pipe.ttl(window_key)
                    global_stats = await pipe.hgetall(_GLOBAL_KEY)

                    if _budget_hard_stop_hit(global_stats, self._settings):
                        raise ProviderBudgetExhaustedError

                    window_exists = window_ttl != _TTL_KEY_MISSING  # aged out or first request
                    reservation = self._estimate_reservation(global_stats, allowance)

                    held = _field_float(window, _FIELD_SPEND) + _field_float(window, _FIELD_RESERVATIONS)
                    if held + reservation > allowance + _FLOAT_EPS:
                        reset_after = window_ttl if window_ttl > 0 else self._settings.WINDOW_LENGTH.total_seconds()
                        reset_at = datetime.fromtimestamp(time.time() + reset_after, tz=UTC)
                        raise ChatboxWindowQuotaExceededError(
                            allowance_usd=f"${allowance:.2f}",
                            reset_at=reset_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            retry_after_seconds=reset_after,
                        )

                    pipe.multi()
                    pipe.hincrbyfloat(window_key, _FIELD_RESERVATIONS, reservation)
                    if not window_exists:
                        # the Usage Window starts at the holder's first admitted request
                        pipe.expire(window_key, int(self._settings.WINDOW_LENGTH.total_seconds()))
                    pipe.hincrbyfloat(_GLOBAL_KEY, _FIELD_RESERVATIONS, reservation)
                    await pipe.execute()
            except WatchError:
                continue
            except _REDIS_UNAVAILABLE_ERRORS:
                self._metrics.ledger_failures_total.labels(stage="window_quota").inc()
                _logger.warning("Usage ledger unreachable during admission (fail-closed)", exc_info=True)
                raise UsageLedgerUnavailableError from None

            return Reservation(user_id=user_id, product_name=product_name, amount_usd=reservation)

        # pathological contention: fail-closed rather than admit unchecked
        self._metrics.ledger_failures_total.labels(stage="window_quota").inc()
        raise UsageLedgerUnavailableError

    async def ensure_global_budget_available(self) -> None:
        """Re-check the Global Budget Guard hard stop (Celery worker, at task start)."""
        try:
            global_stats = await self._redis.hgetall(_GLOBAL_KEY)
        except _REDIS_UNAVAILABLE_ERRORS:
            self._metrics.ledger_failures_total.labels(stage="global_budget").inc()
            _logger.warning("Usage ledger unreachable during budget re-check (fail-closed)", exc_info=True)
            raise UsageLedgerUnavailableError from None

        if _budget_hard_stop_hit(global_stats, self._settings):
            raise ProviderBudgetExhaustedError

    def _estimate_reservation(self, global_stats: dict[str, str], allowance: float) -> NonNegativeFloat:
        requests = _field_float(global_stats, _FIELD_REQUESTS)
        spend = _field_float(global_stats, _FIELD_SPEND)
        if requests <= 0 or spend <= 0:
            # cold start: no rolling average to size from; reserve the whole allowance so
            # at most one request per window is in flight until the first completion lands
            return allowance
        average = spend / requests
        return min(average * self._settings.RESERVATION_SAFETY_FACTOR, allowance)

    # -- reconciliation / release ---------------------------------------------------

    async def reconcile(self, reservation: Reservation, usage: UsageRecord) -> None:
        """Replace the Reservation with the actual Spend and append the ledger entry.

        Ledger failures never fail the completion (the answer is already in the user's
        hands); they are made visible via the failures counter.
        """
        spend = self._spend_usd(usage)
        window_key = self._window_key(reservation.user_id, reservation.product_name)
        for _ in range(_CAS_MAX_ATTEMPTS):
            try:
                async with self._redis.pipeline() as pipe:
                    await pipe.watch(window_key, _GLOBAL_KEY)
                    window_ttl: int = await pipe.ttl(window_key)
                    window_exists = window_ttl != _TTL_KEY_MISSING  # aged out mid-completion: skip it

                    pipe.multi()
                    if window_exists:
                        pipe.hincrbyfloat(window_key, _FIELD_RESERVATIONS, -reservation.amount_usd)
                        pipe.hincrbyfloat(window_key, _FIELD_SPEND, spend)
                    pipe.hincrbyfloat(_GLOBAL_KEY, _FIELD_RESERVATIONS, -reservation.amount_usd)
                    pipe.hincrbyfloat(_GLOBAL_KEY, _FIELD_SPEND, spend)
                    pipe.hincrby(_GLOBAL_KEY, _FIELD_REQUESTS, 1)
                    await pipe.execute()
            except WatchError:
                continue
            except _REDIS_UNAVAILABLE_ERRORS:
                self._metrics.ledger_failures_total.labels(stage="reconcile").inc()
                _logger.warning("Usage ledger unreachable during reconciliation", exc_info=True)
                return

            await self._record_completion(reservation, usage, spend)
            return

    async def release(self, reservation: Reservation, *, reason: str) -> None:
        """Refund a Reservation (timeout / client abort / submit or task failure).

        Real provider burn between the start of the completion and the release can then
        go uncounted against the Provider Budget — the released-reservations counter keeps
        that visible.
        """
        self._metrics.released_reservations_total.labels(reason=reason).inc()
        window_key = self._window_key(reservation.user_id, reservation.product_name)
        for _ in range(_CAS_MAX_ATTEMPTS):
            try:
                async with self._redis.pipeline() as pipe:
                    await pipe.watch(window_key, _GLOBAL_KEY)
                    window_ttl: int = await pipe.ttl(window_key)
                    window_exists = window_ttl != _TTL_KEY_MISSING

                    pipe.multi()
                    if window_exists:
                        pipe.hincrbyfloat(window_key, _FIELD_RESERVATIONS, -reservation.amount_usd)
                    pipe.hincrbyfloat(_GLOBAL_KEY, _FIELD_RESERVATIONS, -reservation.amount_usd)
                    await pipe.execute()
            except WatchError:
                continue
            except _REDIS_UNAVAILABLE_ERRORS:
                self._metrics.ledger_failures_total.labels(stage="release").inc()
                _logger.warning("Usage ledger unreachable during reservation release", exc_info=True)
                return

            return

    # -- internals -------------------------------------------------------------------

    async def _record_completion(self, reservation: Reservation, usage: UsageRecord, spend_usd: float) -> None:
        entry = {
            "user_id": f"{reservation.user_id}",
            "product_name": reservation.product_name,
            "prompt_tokens": "" if usage.prompt_tokens is None else f"{usage.prompt_tokens}",
            "completion_tokens": "" if usage.completion_tokens is None else f"{usage.completion_tokens}",
            "total_tokens": f"{usage.total_tokens}",
            "spend_usd": repr(spend_usd),
            "estimated": "1" if usage.estimated else "0",
            "ts": f"{time.time():.6f}",
        }
        try:
            with suppress(Exception):  # ledger bookkeeping must not break the response path
                await self._redis.xadd(_LEDGER_STREAM_KEY, entry, maxlen=_LEDGER_STREAM_MAXLEN, approximate=True)

            global_spend = await self._redis.hget(_GLOBAL_KEY, _FIELD_SPEND)
            budget = self._settings.PROVIDER_BUDGET_USD
            if budget > 0:
                self._metrics.provider_budget_fraction.set(
                    _field_float({_FIELD_SPEND: global_spend or "0"}, _FIELD_SPEND) / budget
                )
        except _REDIS_UNAVAILABLE_ERRORS:
            _logger.warning("Could not record the usage ledger entry", exc_info=True)

        self._metrics.spend_usd_total.labels(product_name=reservation.product_name).inc(spend_usd)
        self._metrics.spend_usd_global_total.inc(spend_usd)

    def _spend_usd(self, usage: UsageRecord) -> float:
        # Spend = total tokens at the platform-wide Blended Rate (USD per million tokens)
        return usage.total_tokens / 1e6 * self._settings.BLENDED_RATE_USD_PER_MTOK


# -- app setup ------------------------------------------------------------------


def configure_chatbox_usage_ledger(
    app: FastAPI,
    app_lifespan: LifespanManager[FastAPI],
    *,
    settings: ChatboxUsageLimitsSettings,
) -> None:
    """Adds the Usage Ledger lifespan: a Redis client on the dedicated DB + the ledger."""
    prometheus_metrics = getattr(app.state, "prometheus_metrics", None)
    metrics_registry: CollectorRegistry = getattr(prometheus_metrics, "registry", None) or CollectorRegistry()

    async def _lifespan(_: FastAPI, _state: State) -> AsyncIterator[State]:
        client = RedisClientSDK(
            settings.REDIS.build_redis_dsn(RedisDatabase.CHATBOX_USAGE),
            client_name="api-server-chatbox-usage",
        )
        await client.setup()
        app.state.chatbox_usage_ledger = ChatboxUsageLedger(
            _client=client,
            _settings=settings,
            _metrics=_UsageMetrics(metrics_registry),
        )
        try:
            yield {}
        finally:
            app.state.chatbox_usage_ledger = None
            with log_catch(_logger, reraise=False):
                await client.shutdown()

    app_lifespan.add(_lifespan)


def get_chatbox_usage_ledger(app: FastAPI) -> ChatboxUsageLedger | None:
    ledger: ChatboxUsageLedger | None = getattr(app.state, "chatbox_usage_ledger", None)
    if ledger is None or not ledger._settings.ENABLED:  # noqa: SLF001  # pylint: disable=protected-access
        return None
    return ledger
