#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["locust"]
# ///
"""Benchmark arbitrary GET routes of a real osparc deployment, using Locust as a library.

Drives Locust programmatically so the whole thing stays a single, self-contained
executable (no separate locustfile / `locust` CLI needed). Every route is hit with
HTTP Basic auth (api key / secret) and reported separately, plus an aggregated row.

The default route, `/v0/solvers`, drives the catalog RPC `list_services_paginated`
-> bulk services manifest cache, so it exercises the optimization this PR targets;
point `ROUTES` at anything else to benchmark other endpoints.

Auth: an osparc API key/secret (create one under your account settings).

Configuration (all via env vars):
    OSPARC_API_URL      target host, e.g. https://api.osparc.io        (required)
    OSPARC_API_KEY      api key   (Basic-auth username)                (required)
    OSPARC_API_SECRET   api secret (Basic-auth password)               (required)
    ROUTES              comma-separated GET paths    (default: /v0/solvers)
    USERS               concurrent users             (default: 20)
    SPAWN_RATE          users spawned per second     (default: USERS)
    RUN_TIME            test duration in seconds     (default: 10)
    N                   if > 0, stop after N requests instead of RUN_TIME

Usage:
    OSPARC_API_URL=https://api.osparc.io \
    OSPARC_API_KEY=... OSPARC_API_SECRET=... \
        ./bench_catalog_services.py

    # heavier load over several routes for 30s:
    ROUTES=/v0/solvers,/v0/studies USERS=50 RUN_TIME=30 \
    OSPARC_API_URL=https://api.osparc.io \
    OSPARC_API_KEY=... OSPARC_API_SECRET=... ./bench_catalog_services.py
"""

import itertools
import os
import secrets

import gevent
from locust import HttpUser, constant, task
from locust.env import Environment
from locust.log import setup_logging
from locust.stats import (
    print_error_report,
    print_percentile_stats,
    print_stats,
    stats_history,
    stats_printer,
)

HOST = os.environ["OSPARC_API_URL"].rstrip("/")
AUTH = (os.environ["OSPARC_API_KEY"], os.environ["OSPARC_API_SECRET"])
ROUTES = [r.strip() for r in os.getenv("ROUTES", "/v0/solvers").split(",") if r.strip()]
USERS = int(os.getenv("USERS", os.getenv("CONCURRENCY", "20")))
SPAWN_RATE = float(os.getenv("SPAWN_RATE", str(USERS)))
RUN_TIME = float(os.getenv("RUN_TIME", "10"))
N = int(os.getenv("N", "0"))


class OsparcApiUser(HttpUser):
    host = HOST
    wait_time = constant(0)  # hammer as fast as the user can, no think-time

    def on_start(self) -> None:
        self.client.auth = AUTH

    @task
    def hit_route(self) -> None:
        # `name` groups stats per-route (the path), independent of query params
        path = secrets.choice(ROUTES)
        self.client.get(path, name=path)


def main() -> None:
    setup_logging("INFO")
    env = Environment(user_classes=[OsparcApiUser], host=HOST)
    env.create_local_runner()

    gevent.spawn(stats_printer(env.stats))
    gevent.spawn(stats_history, env.runner)

    if N > 0:
        # stop once N requests (successes + failures) have completed
        counter = itertools.count(1)
        env.events.request.add_listener(lambda **_kwargs: next(counter) >= N and env.runner.quit())
    else:
        gevent.spawn_later(RUN_TIME, env.runner.quit)

    env.runner.start(USERS, spawn_rate=SPAWN_RATE)
    env.runner.greenlet.join()

    print_stats(env.stats)
    print_percentile_stats(env.stats)
    print_error_report(env.stats)


if __name__ == "__main__":
    main()
