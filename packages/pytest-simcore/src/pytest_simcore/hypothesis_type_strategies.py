from hypothesis import provisional
from hypothesis import strategies as st
from pydantic import AnyHttpUrl, AnyUrl, HttpUrl

# FIXME: For now it seems the pydantic hypothesis plugin does not provide strategies for these types.
# therefore we currently provide it
st.register_type_strategy(AnyUrl, provisional.urls())
st.register_type_strategy(HttpUrl, provisional.urls())
st.register_type_strategy(AnyHttpUrl, provisional.urls())
