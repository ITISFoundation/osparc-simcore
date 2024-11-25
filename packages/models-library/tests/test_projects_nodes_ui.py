from models_library.projects_nodes_ui import Marker
from pydantic_extra_types.color import Color


def test_marker_serialization():
    m = Marker(color=Color("#b7e28d"))

    assert m.model_dump_json() == '{"color":"#b7e28d"}'
