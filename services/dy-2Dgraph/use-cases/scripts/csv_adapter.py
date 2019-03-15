from pathlib import Path

from simcore_sdk import node_ports


async def export_to_csv(plot_data, title, header=None, port_number=0):
    if header is None: 
        header = []

    title = title.replace(" ", "_") + ".csv"
    dummy_file_path = Path(title)
    plot_data.to_csv(dummy_file_path, sep=',', header=header, index=False, encoding='utf-8')

    PORTS = node_ports.ports()
    await PORTS.outputs[port_number].set(dummy_file_path)


