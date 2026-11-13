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

def test_reassign_allowed_only_while_work_is_in_flight():
    i = make_incident(); i.classify(); i.assign("U-T1"); i.reassign("U-T2"); assert i.status == Status.ASSIGNED and i.assigned_to == "U-T2"
    j = make_incident()
    with pytest.raises(InvalidTransitionError): j.reassign("U-T2")          # NEW: nothing to reassign
    k = make_incident(); k.classify(); k.assign("U-T1"); k.acknowledge(); k.start(); k.resolve("x")
    with pytest.raises(InvalidTransitionError): k.reassign("U-T2")          # RESOLVED: too late
