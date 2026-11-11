import pytest
from app.container import build_container
from app.seed import seed

@pytest.fixture
def c():
    container = build_container(":memory:"); seed(container); return container
