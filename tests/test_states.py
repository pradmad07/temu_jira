import pytest
from app.domain.enums import Status
from app.domain.exceptions import InvalidTransitionError, ValidationError
from tests.helpers import make_incident

def test_full_lifecycle_reaches_closed():
    i = make_incident(); i.classify(); i.assign("U-T1"); i.acknowledge(); i.start(); i.resolve("Restarted gateway"); i.verify(); i.close()
    assert i.status == Status.CLOSED

def test_new_to_closed_is_rejected():
    with pytest.raises(InvalidTransitionError): make_incident().close()

def test_rejected_resolution_returns_to_in_progress():
    i = make_incident(); i.classify(); i.assign("U-T1"); i.acknowledge(); i.start(); i.resolve("x"); i.reject()
    assert i.status == Status.IN_PROGRESS

def test_empty_resolution_rejected():
    i = make_incident(); i.classify(); i.assign("U-T1"); i.acknowledge(); i.start()
    with pytest.raises(ValidationError): i.resolve("  ")
