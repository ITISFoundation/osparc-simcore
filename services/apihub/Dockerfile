# Ultra light web server ~6MB
FROM pierrezemb/gostatic as base

EXPOSE 8043

FROM base as development

VOLUME /srv/http

FROM base as production

COPY api/specs /srv/http/api/specs
