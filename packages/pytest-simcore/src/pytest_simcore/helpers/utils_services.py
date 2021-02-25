"""
    NOTE: avoid creating dependencies
"""
from typing import Any, Dict, List

FAKE_FILE_CONSUMER_SERVICES = [
    # services support one filetype
    {
        "key": "simcore/services/dynamic/sim4life",
        "version": "1.0.29",
        "display_name": "Sim4Life",
        "consumes": [
            "DCM",
        ],
    },
    # new version
    {
        "key": "simcore/services/dynamic/sim4life",
        "version": "1.3.0",
        "display_name": "Sim4Life",
        "consumes": [
            "DCM",
        ],
    },
    # newer version, with more support
    {
        "key": "simcore/services/dynamic/sim4life",
        "version": "2.0.0",
        "display_name": "Sim4Life",
        "consumes": ["DCM", "S4LCacheData"],
    },
    # another service with multiple format support (preferred for CSV)
    {
        "key": "simcore/services/dynamic/raw-graphs",
        "version": "2.11.1",
        "display_name": "2D plot - RAWGraphs",
        "consumes": ["CSV", "XLS"],
    },
    # yet another service with also CSV support and PNG only in port 3
    {
        "key": "simcore/services/dynamic/openmicroscopy-web",
        "version": "1.0.1",
        "display_name": "Open microscopy",
        # FYI: https://docs.openmicroscopy.org/bio-formats/6.6.0/supported-formats.html
        "consumes": [
            "CSV",
            "JPEG",
            "PNG:input_3",
        ],
    },
]


def list_fake_file_consumers() -> List[Dict[str, Any]]:
    consumers = []
    for service in FAKE_FILE_CONSUMER_SERVICES:
        for consumable in service["consumes"]:
            filetype, port, *_ = consumable.split(":") + ["input_1"]
            consumer = {
                "key": service["key"],
                "version": service["version"],
                "display_name": service["display_name"],
                "filetype": filetype,
                "input_port_key": port,
            }
            consumers.append(consumer)
    return consumers
