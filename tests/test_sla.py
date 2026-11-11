from datetime import datetime, timedelta, timezone
from app.domain.enums import Priority

def test_p1_deadlines_follow_policy(c):   # TODO(Gaurav)
    t0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    assert c.sla.deadlines_for(Priority.P1, t0) == (t0 + timedelta(minutes=5), t0 + timedelta(minutes=30))

def test_repeated_scans_do_not_duplicate_violations(c):
    c.sla.scan(); c.sla.scan()   # extend: use a fake Clock + an overdue incident, assert exactly one violation row
