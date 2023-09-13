ARG NODE_VERSION="14"
FROM node:${NODE_VERSION}-slim as base

RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  curl \
  git \
  jq \
  libnss3 \
  libatk-bridge2.0 \
  gconf-service \
  libasound2 \
  libatk1.0-0 \
  libc6 \
  libcairo2 \
  libcups2 \
  libdbus-1-3 \
  libexpat1 \
  libfontconfig1 \
  libgcc1 \
  libgconf-2-4 \
  libgdk-pixbuf2.0-0 \
  libglib2.0-0 \
  libgtk-3-0 \
  libnspr4 \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libstdc++6 \
  libx11-6 \
  libx11-xcb1 \
  libxcb1 \
  libxcomposite1 \
  libxcursor1 \
  libxdamage1 \
  libxext6 \
  libxfixes3 \
  libxi6 \
  libxrandr2 \
  libxrender1 \
  libxss1 \
  libxtst6 \
  ca-certificates \
  fonts-liberation \
  libappindicator1 \
  libnss3 \
  lsb-release \
  xdg-utils \
  wget \
  make \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  && apt-get autoremove -y \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
  echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
  apt-get update && \
  apt-get install -y --no-install-recommends \
  docker-ce docker-ce-cli containerd.io \
  && apt-get autoremove -y \
  && apt-get clean -y \
  && rm --recursive --force /var/lib/apt/lists/*


RUN grep --quiet mozilla/DST_Root_CA_X3.crt  "/etc/ca-certificates.conf" && sed --expression '/mozilla\/DST_Root_CA_X3.crt/s/^/!/g' --in-place /etc/ca-certificates.conf && update-ca-certificates

SHELL [ "/bin/bash", "-c" ]

ENTRYPOINT []

ARG BUILD_DATE
ARG VCS_URL
ARG VCS_REF

ENV org.label-schema.schema-version=1.0 \
  org.label-schema.build-date=${BUILD_DATE} \
  org.label-schema.vcs-url=${VCS_URL} \
  org.label-schema.vcs-ref=${VCS_REF}
