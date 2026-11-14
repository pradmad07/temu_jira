from app.domain.models import Technician
from app.services.assignment import SkillBasedAssignment
from tests.helpers import make_incident


def test_recommendations_rank_skill_and_capacity_and_exclude_full():
    skilled = Technician("Skilled", "skilled@x.io", "h", ["APPLICATION"], 4, max_workload=5, id="a")
    unskilled = Technician("Available", "available@x.io", "h", ["NETWORK"], 10, max_workload=5, id="b")
    full = Technician("Full", "full@x.io", "h", ["APPLICATION"], 10, max_workload=1, id="c")

    results = SkillBasedAssignment().recommend(
        make_incident(category="APPLICATION"), [unskilled, full, skilled], {"a": 1, "b": 0, "c": 1}
    )

    assert [r.technician.id for r in results] == ["a", "b"]
    assert any("APPLICATION skill" in reason for reason in results[0].reasons)
    assert any("1/5 active incidents" in reason for reason in results[0].reasons)
