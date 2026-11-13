import pytest
from app.container import build_container
from app.seed import seed
from tests.helpers import FakeClock

@pytest.fixture
def c():
    # auto_assign=False keeps tests deterministic once Pradhyumn's strategies work; one test opts in explicitly.
    container = build_container(":memory:", clock=FakeClock(), auto_assign=False); seed(container); return container
