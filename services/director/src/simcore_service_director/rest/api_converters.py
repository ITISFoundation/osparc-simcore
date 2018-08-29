def __convert_port_from_old_api(ports, add_default_value):
    new_ports = {}
    for old_port in ports:
        new_port = {
                "displayOrder":ports.index(old_port),
                "label":old_port["label"],
                "description":old_port["desc"],
                "type":old_port["type"]                
        }
        if new_port["type"] == "file-url":
            new_port["type"] = "data:*/*"
        elif new_port["type"] == "folder-url":
            new_port["type"] = "data:application/zip"
        if add_default_value and old_port["value"]:
            new_port["defaultValue"] = old_port["value"]

        new_ports[old_port["key"]] = new_port
    return new_ports

def convert_service_from_old_api(service):
    converted_service = {}
    for key, value in service.items():
        if key == "key":
            if str(value).count("/comp/") == 1:
                converted_service["type"] = "computational"
            else:
                converted_service["type"] = "dynamic"
        elif key == "tag":
            key = "version"
        elif key == "inputs":
            value = __convert_port_from_old_api(value, True)
        elif key == "outputs":
            value = __convert_port_from_old_api(value, False)
        elif key == "viewer":
            # skip it
            continue
            
        converted_service[key] = value
    return converted_service