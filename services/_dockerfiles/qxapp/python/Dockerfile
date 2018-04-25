FROM node:8.9.2

LABEL maintainer=pcrespov

ENV NPM_CONFIG_LOGLEVEL warn

WORKDIR /home/node/

RUN npm install qxcompiler
ENV PATH="/home/node/node_modules/.bin/:${PATH}"

WORKDIR /home/node/qxapp
COPY web-client/source source
COPY web-client/*.json ./

# Add dark theme to web-client
RUN qx contrib update
RUN qx contrib list
RUN qx contrib install ITISFoundation/qx-osparc-theme
RUN qx compile


#------------------------------------------------------------------------

FROM python:3

# Selects appropriate 'server-py-*/' folder
ARG serverdir
ARG web_outdir=/usr/src/app/client

ENV SIMCORE_WEB_OUTDIR=$web_outdir


WORKDIR /usr/src/app

COPY --from=0 /home/node/qxapp/source-output $web_outdir

COPY $serverdir/requirements.txt requirements.txt

RUN python --version \
    && pip3 install --no-cache-dir -r ./requirements.txt \
    && pip list --format=columns

COPY $serverdir/* ./

ENV SIMCORE_WEB_HOSTNAME='0.0.0.0'
ENV SIMCORE_WEB_PORT=8080
ENV DIRECTOR_HOST='http://director'
ENV DIRECTOR_PORT=8001
EXPOSE 8080

ENTRYPOINT ["sh", "-c", "python -m aiohttp.web -H ${SIMCORE_WEB_HOSTNAME} -P ${SIMCORE_WEB_PORT} server:create_app"]
