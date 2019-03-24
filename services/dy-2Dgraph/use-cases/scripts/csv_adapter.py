from pathlib import Path

from simcore_sdk import node_ports


async def pandas_dataframe_to_csv(data_frame, title, header=False, port_number=0):
    title = title.replace(" ", "_") + ".csv"
    dummy_file_path = Path(title)
    data_frame.to_csv(dummy_file_path, sep=',', header=header, index=False, encoding='utf-8')

    PORTS = node_ports.ports()
    await PORTS.outputs[port_number].set(dummy_file_path)


