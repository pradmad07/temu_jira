from app.domain.enums import Priority, Status
from app.services.intelligence import IncidentAdvisor
from tests.helpers import make_incident


def test_summary_is_extractive_and_reports_key_facts():
    inc = make_incident(
        title="Database slow",
        description="Queries time out. Users cannot open reports.",
        impact=4,
        urgency=5,
        affected_users=25,
    )
    inc.set_priority(Priority.P1)

    summary = IncidentAdvisor(object()).summarize(inc)

    assert summary.headline == "Database slow"
    assert "Queries time out" in summary.description
    assert "25 user" in " ".join(summary.facts)
    assert "Priority P1" in " ".join(summary.facts)


class _IncidentRepository:
    def __init__(self, incidents):
        self._incidents = incidents

    def search(self, f=None, limit=500):
        return self._incidents


def test_resolution_suggestion_uses_only_resolved_historical_incidents():
    current = make_incident(
        title="Payment database unavailable",
        description="payment transactions fail and database queries time out",
        category="DATABASE",
        service_id="SVC-PAY",
    )
    current.set_priority(Priority.P1)

    resolved = make_incident(
        id="INC-OLD",
        title="Payment database timeout",
        description="database transactions fail with timeout errors",
        category="DATABASE",
        service_id="SVC-PAY",
        resolution="Restarted the primary database and cleared stuck transactions.",
        status=Status.CLOSED,
    )
    resolved.set_priority(Priority.P1)

    unresolved = make_incident(
        id="INC-OPEN",
        title="Payment database timeout",
        description="database transactions fail with timeout errors",
        category="DATABASE",
        service_id="SVC-PAY",
        resolution="Do not trust this",
    )

    suggestions = IncidentAdvisor(
        _IncidentRepository([resolved, unresolved])
    ).suggest_resolutions(current)

    assert len(suggestions) == 1
    assert suggestions[0].incident_id == "INC-OLD"
    assert "source" not in suggestions[0].resolution.lower()
