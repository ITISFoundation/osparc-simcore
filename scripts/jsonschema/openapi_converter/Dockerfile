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

VOLUME [ "/input" ]
VOLUME [ "/output" ]

WORKDIR /src

RUN npm install --save json-schema-to-openapi-schema && \
    npm install --save js-yaml
COPY converter.js /src/converter.js


CMD [ "node", "/src/converter.js" ]