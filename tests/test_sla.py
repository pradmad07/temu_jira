from datetime import datetime, timedelta, timezone
import pytest
from app.domain.enums import Priority, Category
from app.domain.events import EV_SLA_WARNING, EV_SLA_VIOLATED, EV_ESCALATED
from app.domain.exceptions import MissingSlaError
from tests.helpers import report, user

def test_p1_deadlines_follow_policy(c):
    t0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    deadlines = c.sla.deadlines_for(Priority.P1, t0)
    assert deadlines == (t0 + timedelta(minutes=5), t0 + timedelta(minutes=30))

def test_all_priorities_follow_policy(c):
    t0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    assert c.sla.deadlines_for(Priority.P1, t0) == (t0 + timedelta(minutes=5), t0 + timedelta(minutes=30))
    assert c.sla.deadlines_for(Priority.P2, t0) == (t0 + timedelta(minutes=15), t0 + timedelta(minutes=120))
    assert c.sla.deadlines_for(Priority.P3, t0) == (t0 + timedelta(minutes=60), t0 + timedelta(minutes=480))
    assert c.sla.deadlines_for(Priority.P4, t0) == (t0 + timedelta(minutes=240), t0 + timedelta(minutes=1440))

def test_service_specific_sla_override(c):
    t0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    # Stricter SVC-PAY P1 override: 3 min response, 20 min resolution
    assert c.sla.deadlines_for(Priority.P1, t0, service_id="SVC-PAY") == (t0 + timedelta(minutes=3), t0 + timedelta(minutes=20))

def test_repeated_scans_do_not_duplicate_violations(c):
    # Create an incident via real service
    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION", impact=5, urgency=5)
    # Set to P1 so response deadline is 5m and resolution is 30m
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Urgent production outage")

    # Advance clock past both response (5m) and resolution (30m) deadlines
    c.clock.advance(minutes=35)

    events_1 = c.sla.scan()
    events_2 = c.sla.scan()

    # Database should have exactly one record per violation kind
    violations = c.violations.list_for_incident(inc.id)
    kinds = [k for k, _ in violations]

    assert "RESPONSE_VIOLATION" in kinds
    assert "RESOLUTION_VIOLATION" in kinds
    assert kinds.count("RESPONSE_VIOLATION") == 1
    assert kinds.count("RESOLUTION_VIOLATION") == 1

    # First scan publishes events; second scan publishes nothing because records exist
    assert any(e.type == EV_SLA_VIOLATED for e in events_1)
    assert len(events_2) == 0

def test_sla_warning_emitted_at_75_percent(c):
    # SVC-DB uses default '*' SLA (P1: 5m response, 30m resolution; 75% response window = 3m 45s)
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Urgent")

    # Advance 2 minutes: below 75% -> no warning
    c.clock.advance(minutes=2)
    events = c.sla.scan()
    assert not any(e.type == EV_SLA_WARNING for e in events)

    # Advance another 2 minutes (total 4m >= 3m 45s): warning should fire
    c.clock.advance(minutes=2)
    events = c.sla.scan()
    warnings = [e for e in events if e.type == EV_SLA_WARNING]
    assert len(warnings) >= 1
    assert any("Response SLA warning" in e.description for e in warnings)

    # Scanning again should not duplicate the warning
    events_repeat = c.sla.scan()
    assert len(events_repeat) == 0

def test_p1_unacknowledged_escalation(c):
    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Critical issue")

    # Advance 10 minutes past response deadline (5m) without acknowledging
    c.clock.advance(minutes=10)
    events = c.sla.scan()
    escalated = [e for e in events if e.type == EV_ESCALATED]
    assert len(escalated) == 1
    assert inc.id in escalated[0].incident_id

def test_acknowledged_incident_does_not_breach_response_sla(c):
    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Critical")
    c.incident_service.assign_incident(user(c, "admin@itsm.local"), inc.id, "U-T1")

    # Acknowledge at minute 2 (before 5m deadline)
    c.clock.advance(minutes=2)
    c.incident_service.acknowledge(user(c, "t1@itsm.local"), inc.id)

    # Advance past 10 minutes
    c.clock.advance(minutes=8)
    c.sla.scan()

    violations = [k for k, _ in c.violations.list_for_incident(inc.id)]
    assert "RESPONSE_VIOLATION" not in violations
    assert "RESPONSE_WARNING" not in violations
