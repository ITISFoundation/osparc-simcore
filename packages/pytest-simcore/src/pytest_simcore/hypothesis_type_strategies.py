from hypothesis import provisional
from hypothesis import strategies as st
from hypothesis.strategies import composite
from pydantic import TypeAdapter
from pydantic_core import Url


@composite
def url_strategy(draw):
    return TypeAdapter(Url).validate_python(draw(provisional.urls()))


st.register_type_strategy(Url, url_strategy())
