# Redis-only usage ledger for the Chatbox limits (v1)

The api-server must limit Chatbox spend against a one-time vendor Provider Budget, and its only
low-latency shared store is Redis. We decided to keep the entire Usage Ledger (per-key request
counts, per-user Spend counters, reservations, the global cumulative counter) in Redis for v1 —
no Postgres table, no RUT integration — because enforcement needs atomic increment-with-TTL and
release-1 does not charge for usage.

## Considered Options

- Dual-write Redis (enforcement) + Postgres (durable ledger): rejected for v1 — adds a second
  system of record and an Alembic migration for a feature whose pricing (Blended Rate) and
  semantics (no charging) are expected to change once real vendor invoices land.
- Delegate to web-server wallets / resource-usage-tracker now: rejected — charging is explicitly
  out of scope, and RUT's pricing-plan model is shaped around compute service runs, not tokens.

## Consequences

- Usage state shares fate with the platform cache Redis: eviction or a flush resets all counters
  and the Provider Budget guard's cumulative total. Accepted as conservative for now, with
  fail-closed enforcement for the spend layers.
- Re-pricing history or producing billing records is impossible from this ledger. The follow-up is
  a durable dump via RUT before charging ships — tracked in the wiki, retired by the charging
  release.
