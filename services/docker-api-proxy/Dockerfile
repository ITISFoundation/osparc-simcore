FROM alpine:3.21 AS base

LABEL maintainer=GitHK

# simcore-user uid=8004(scu) gid=8004(scu) groups=8004(scu)
ENV SC_USER_ID=8004 \
  SC_USER_NAME=scu \
  SC_BUILD_TARGET=base \
  SC_BOOT_MODE=default

RUN addgroup -g ${SC_USER_ID} ${SC_USER_NAME} && \
  adduser -u ${SC_USER_ID} -G ${SC_USER_NAME} \
  --disabled-password \
  --gecos "" \
  --shell /bin/sh \
  --home /home/${SC_USER_NAME} \
  ${SC_USER_NAME}

RUN apk add --no-cache socat curl && \
  curl -L -o /usr/local/bin/gosu https://github.com/tianon/gosu/releases/download/1.16/gosu-amd64 && \
  chmod +x /usr/local/bin/gosu && \
  gosu --version


# Health check to ensure the proxy is running
HEALTHCHECK \
  --interval=10s \
  --timeout=5s \
  --start-period=30s \
  --start-interval=1s \
  --retries=5 \
  CMD curl http://localhost:8888/version || exit 1

COPY --chown=scu:scu services/docker-api-proxy/docker services/docker-api-proxy/docker
RUN chmod +x services/docker-api-proxy/docker/*.sh

ENTRYPOINT [ "/bin/sh", "services/docker-api-proxy/docker/entrypoint.sh" ]
CMD ["/bin/sh", "services/docker-api-proxy/docker/boot.sh"]

FROM base AS development
ENV SC_BUILD_TARGET=development

FROM base AS production
ENV SC_BUILD_TARGET=production
