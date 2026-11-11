import pytest
from app.domain.enums import Category
from app.domain.exceptions import TechnicianUnavailableError
from app.domain.models import Technician
from app.services.assignment import SkillBasedAssignment, LoadBasedAssignment
from tests.helpers import make_incident

ann = Technician("Ann", "ann@x.io", "h", ["DATABASE"], 8, id="ann"); bob = Technician("Bob", "bob@x.io", "h", ["NETWORK"], 2, id="bob")

def test_skill_based_prefers_matching_skill():   # TODO(Pradhyumn)
    assert SkillBasedAssignment().choose(make_incident(category=Category.DATABASE), [bob, ann], {}) is ann

def test_load_based_prefers_least_loaded():
    assert LoadBasedAssignment().choose(make_incident(), [ann, bob], {"ann": 4, "bob": 1}) is bob

def test_nobody_eligible_raises():
    full = Technician("Full", "f@x.io", "h", ["DATABASE"], max_workload=1, id="f")
    with pytest.raises(TechnicianUnavailableError): SkillBasedAssignment().choose(make_incident(), [full], {"f": 1})
