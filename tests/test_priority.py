from app.domain.enums import Priority
from app.services.priority import ScoredPriority
from tests.helpers import make_incident, make_service

def test_critical_inputs_give_p1():
    # 5x5x5 with 500 users -> P1
    assert ScoredPriority().calculate(make_incident(impact=5, urgency=5, affected_users=500), make_service(criticality=5)) == Priority.P1

def test_minimal_inputs_give_p4():
    # 1x1x1 -> P4
    assert ScoredPriority().calculate(make_incident(impact=1, urgency=1), make_service(criticality=1)) == Priority.P4

def test_default_helper_values_give_p3():
    # 3x3x3 = 27 -> P3
    assert ScoredPriority().calculate(make_incident(impact=3, urgency=3), make_service(criticality=3)) == Priority.P3
