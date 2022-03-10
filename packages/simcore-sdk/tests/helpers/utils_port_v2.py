from typing import Any, Dict, Optional, Type, Union

from simcore_sdk.node_ports_v2.ports_mapping import InputsList, OutputsList


def create_valid_port_config(conf_type: str, **kwargs) -> Dict[str, Any]:
    valid_config = {
        "key": f"some_{conf_type}",
        "label": "some label",
        "description": "some description",
        "type": conf_type,
        "displayOrder": 2.3,
    }
    valid_config.update(kwargs)
    return valid_config


def create_valid_port_mapping(
    mapping_class: Union[Type[InputsList], Type[OutputsList]],
    suffix: str,
    file_to_key: Optional[str] = None,
) -> Union[InputsList, OutputsList]:

    port_cfgs: Dict[str, Any] = {}
    for t, v in {
        "integer": 43,
        "number": 45.6,
        "boolean": True,
        "string": "dfgjkhdf",
    }.items():
        port = create_valid_port_config(
            t,
            key=f"{'input' if mapping_class==InputsList else 'output'}_{t}_{suffix}",
            value=v,
        )
        port_cfgs[port["key"]] = port

    key_for_file_port = (
        f"{'input' if mapping_class==InputsList else 'output'}_file_{suffix}"
    )
    port_cfgs[key_for_file_port] = create_valid_port_config(
        "data:*/*",
        key=key_for_file_port,
        fileToKeyMap={file_to_key: key_for_file_port} if file_to_key else None,
    )
    port_mapping = mapping_class(**{"__root__": port_cfgs})
    return port_mapping
