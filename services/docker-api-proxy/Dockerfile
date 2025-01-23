FROM alpine:3.21 AS base

RUN apk add --no-cache socat curl

# Health check to ensure the proxy is running
HEALTHCHECK \
  --interval=30s \
  --timeout=10s \
  --start-period=5s \
  --retries=3 \
  CMD curl http://localhost:8888/version || exit 1

ENTRYPOINT ["socat"]

CMD ["-d", "-d","-v", "TCP-LISTEN:8888,fork,reuseaddr", "UNIX-CONNECT:/var/run/docker.sock"]

FROM base AS development
FROM base AS production
