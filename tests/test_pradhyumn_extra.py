import pytest

from app.domain.enums import Priority
from app.domain.exceptions import ValidationError
from app.domain.models import Technician
from app.services.assignment import LoadBasedAssignment, SkillBasedAssignment, strategy_by_name
from app.services.duplicates import DuplicateDetector
from app.services.priority import ScoredPriority
from tests.helpers import make_incident, make_service


def test_priority_threshold_boundaries():
    strategy = ScoredPriority()
    assert strategy.calculate(make_incident(impact=2, urgency=1), make_service(criticality=5)) == Priority.P3
    assert strategy.calculate(make_incident(impact=2, urgency=3, affected_users=2), make_service(criticality=5)) == Priority.P2


def test_skill_assignment_tie_breaks_by_experience_then_id():
    older = Technician("Older", "older@x.io", "h", ["APPLICATION"], 8, id="b")
    younger = Technician("Younger", "younger@x.io", "h", ["APPLICATION"], 4, id="a")
    assert SkillBasedAssignment().choose(make_incident(), [older, younger], {"a": 1, "b": 1}) is older

    same = Technician("Same", "same@x.io", "h", ["APPLICATION"], 8, id="c")
    assert SkillBasedAssignment().choose(make_incident(), [same, older], {"b": 1, "c": 1}) is older


def test_load_assignment_respects_workload_limit():
    full = Technician("Full", "full2@x.io", "h", [], 10, max_workload=2, id="full")
    open_tech = Technician("Open", "open@x.io", "h", [], 1, max_workload=3, id="open")
    assert LoadBasedAssignment().choose(make_incident(), [full, open_tech], {"full": 2, "open": 2}) is open_tech


def test_invalid_assignment_strategy_is_rejected():
    with pytest.raises(ValidationError):
        strategy_by_name("unknown")


def test_duplicate_detector_requires_same_service_and_excludes_self():
    incident = make_incident(title="Payment failing", description="Payment page fails")
    other_service = make_incident(id="other", service_id="SVC-OTHER", title="Payment failing", description="Payment page fails")
    assert DuplicateDetector().find_candidates(incident, [incident, other_service]) == []
