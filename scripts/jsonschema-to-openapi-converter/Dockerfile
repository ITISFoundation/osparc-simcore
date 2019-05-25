# Docs:
# This tool is based on [Phil Sturgeon blog](https://philsturgeon.uk/api/2018/04/13/openapi-and-json-schema-divergence-solved/)
# and specifically on [json-schema-to-openapi-schema](https://github.com/wework/json-schema-to-openapi-schema)
# 
# The tool converts any .json file present in a specific input folder into openapi schema .yaml in a specific output folder

# Usage: 
# docker build -t json2openapiconverter .
# docker run -v %INPUT_FOLDER%:/input -v %OUTPUT_FOLDER%:/output json2openapiconverter

FROM node

LABEL maintainer=sanderegg

ARG HOST_UID=${HOST_UID:-4000}
ARG HOST_USER=${HOST_USER:-nodummy}

RUN adduser --system --home /home/${HOST_USER} --uid ${HOST_UID} ${HOST_USER} \
    && chown -R "${HOST_UID}:${HOST_UID}" /home/${HOST_USER}

USER ${HOST_USER}
WORKDIR /home/${HOST_USER}

RUN npm install --save json-schema-to-openapi-schema && \
    npm install --save js-yaml

COPY converter.js ./src/converter.js


CMD [ "node", "src/converter.js" ]