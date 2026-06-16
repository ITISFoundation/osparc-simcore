# Web-Server Testing Guidelines

> Testing invariants and conventions for the web-server. Companion to [DESIGN.md](./DESIGN.md).

---

## Testing Invariants

Mocks are reserved for boundaries — not for isolating our own domains from each other.

- **Mock ONLY:**
  - **(a) external services** — the HTTP/RPC backends we connect to (the client/gateway layer); and
  - **(b) deliberate side-effects** — to exercise exception handling, delays, or concurrency.
- **Do NOT** mock domain facades to isolate domains in cross-domain tests. Use the real services
  and a real database.

| Layer under test    | Real                              | Mocked                              |
| ------------------- | --------------------------------- | ----------------------------------- |
| Repository          | DB                                | —                                   |
| Service             | repositories + DB                 | external clients; side-effects only |
| Aggregation service | all involved domain services + DB | external clients; side-effects only |
| Controller          | service stack                     | external clients; side-effects only |
