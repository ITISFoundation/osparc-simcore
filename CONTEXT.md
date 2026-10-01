# osparc-simcore

Monorepo of the simcore platform: services, shared packages and tests. This file is the shared
domain glossary; it is a glossary and nothing else — no implementation details.

## Language

### AI chatbox usage limits

**Chatbox**:
The external vendor AI service that produces model completions, consumed by the api-server through
a single OpenAI-compatible endpoint.

**Provider Budget**:
The one-time total USD amount the organization may spend with the Chatbox vendor, across all
users. Not periodic.
_Avoid_: T$ (informal), total quota

**Spend**:
The normalized USD cost of one chat completion, derived from token counts converted at the Blended
Rate.
_Avoid_: cost, usage, token usage

**Usage Ledger**:
The record of each chat completion's Spend together with its raw token counts. Basis for
enforcement today and for monitoring and billing later.

**Usage Window**:
The period over which a Window Quota applies, starting at a holder's first request and running a
fixed length. Spend aged out of the window stops counting against it.
_Avoid_: rolling window, billing period

**Reservation**:
A provisional Spend placed against the Window Quota before a completion starts, estimated from
recent average usage, replaced by the actual Spend when the completion finishes.
_Avoid_: hold, deposit

**Blended Rate**:
The single platform-wide price per million tokens used to compute Spend from token counts, in
place of per-model prices — the Chatbox answers with a tier chosen at run time, so the requested
model's price is not the paid one.
_Avoid_: price list, per-model price

**Rate Limit**:
The enforcement layer that caps requests per minute. Guards against bursts and abuse.
_Avoid_: throttle

**Window Quota**:
The enforcement layer that caps Spend within one usage window. Guards against burning the budget
all at once.
_Avoid_: daily limit, soft cap

**Lifetime Cap**:
The enforcement layer that caps the cumulative Spend a holder can ever consume.
_Avoid_: hard cap (ambiguous with the global one)

**Global Budget Guard**:
The enforcement layer that tracks aggregate Spend against the Provider Budget, warns before
exhaustion and stops completions at a hard-stop threshold.
_Avoid_: global quota
