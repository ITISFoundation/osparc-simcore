FROM node:14.18.3-buster-slim

LABEL maintainer=sanderegg

VOLUME [ "/input" ]
VOLUME [ "/output" ]

WORKDIR /src

RUN npm install --save json-schema-to-openapi-schema && \
  npm install --save js-yaml
COPY converter.js /src/converter.js


CMD [ "node", "/src/converter.js" ]
