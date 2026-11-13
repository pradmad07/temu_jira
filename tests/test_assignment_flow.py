import pytest
from app.container import build_container
from app.seed import seed
from app.domain.enums import Status
from app.domain.exceptions import AuthorizationError, TechnicianUnavailableError, ValidationError
from app.services.assignment import AssignmentStrategy, STRATEGIES
from tests.helpers import FakeClock, report, user

class FirstAvailable(AssignmentStrategy):
    def choose(self, incident, candidates, workloads): return candidates[0]
class Nobody(AssignmentStrategy):
    def choose(self, incident, candidates, workloads): raise TechnicianUnavailableError("nobody free")

def _auto():
    c = build_container(":memory:", clock=FakeClock(), auto_assign=True); seed(c); return c

def test_a_new_strategy_plugs_in_with_one_class_and_one_registry_entry():
    STRATEGIES["first"] = FirstAvailable
    try:
        c = _auto(); c.admin.set_assignment_strategy(user(c, "admin@itsm.local"), "first")
        inc = report(c)
        got = c.incidents.get(inc.id)
        assert got.status == Status.ASSIGNED and got.assigned_to is not None
        assert "INCIDENT_ASSIGNED" in [a.action for a in c.audit.list_for_incident(inc.id)]
    finally: STRATEGIES.pop("first", None)

def test_incident_stays_classified_when_nobody_is_available():
    STRATEGIES["nobody"] = Nobody
    try:
        c = _auto(); c.admin.set_assignment_strategy(user(c, "admin@itsm.local"), "nobody")
        assert c.incidents.get(report(c).id).status == Status.CLASSIFIED
    finally: STRATEGIES.pop("nobody", None)

def test_unknown_strategy_rejected_and_employee_cannot_switch(c):
    with pytest.raises(ValidationError): c.admin.set_assignment_strategy(user(c, "admin@itsm.local"), "random-magic")
    with pytest.raises(AuthorizationError): c.admin.set_assignment_strategy(user(c, "e1@itsm.local"), "load")
