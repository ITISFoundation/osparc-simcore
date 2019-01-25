import asyncio
import json
import sys

from simcore_sdk import node_ports


async def retrieve_data():
    print("retrieving data...")
    PORTS = node_ports.ports()

    values = {}
    for node_input in PORTS.inputs:        
        if not node_input or node_input.value is None:
            continue
        print("getting data from port '{}' with value '{}'...".format(node_input.key, node_input.value))
        value = await node_input.get()
        values[node_input.key] = {"type": node_input.type, "value": value}
    

    print("json={}".format(json.dumps(values)))
    sys.stdout.flush()



def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(retrieve_data())

if __name__ == "__main__":
    main()