import logging

import trafaret as T

CONFIG_SECTION_NAME = "tracing"

log = logging.getLogger(__name__)


# TODO: deprecated by TracingSettings in https://github.com/ITISFoundation/osparc-simcore/pull/2376
# NOT used
schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.ToInt),
        T.Key("zipkin_endpoint", default="http://jaeger:9411"): T.String(),
    }
)
