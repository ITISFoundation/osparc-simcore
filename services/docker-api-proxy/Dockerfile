FROM alpine:3.21 AS base

RUN apk add --no-cache socat curl

# Health check to ensure the proxy is running
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=30s \
  --start-interval=1s \
  --retries=5 \
  CMD curl http://localhost:8888/version || exit 1

ENTRYPOINT ["socat"]

CMD ["TCP-LISTEN:8888,fork,reuseaddr", "UNIX-CONNECT:/var/run/docker.sock"]

FROM base AS development
FROM base AS production
