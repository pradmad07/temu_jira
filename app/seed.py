"""Demo data. All passwords: password123."""
from app.domain.enums import Role
from app.domain.factories import UserFactory as F

def seed(c):
    h = c.auth.hash_password("password123")
    for u in [  # managers first: reports_to is a foreign key
        F.create(Role.IT_MANAGER, "Maya Manager", "mgr@itsm.local", h, id="U-MGR"),
        F.create(Role.ADMIN, "Admin", "admin@itsm.local", h, id="U-ADMIN"),
        F.create(Role.TEAM_LEAD, "Lena Lead", "lead@itsm.local", h, id="U-LEAD", reports_to="U-MGR"),
        F.create(Role.EMPLOYEE, "Asha Employee", "e1@itsm.local", h, id="U-E1"),
        F.create(Role.EMPLOYEE, "Ravi Employee", "e2@itsm.local", h, id="U-E2"),
        F.create(Role.TECHNICIAN, "Tina DB", "t1@itsm.local", h, id="U-T1", reports_to="U-LEAD", skills=["DATABASE", "APPLICATION"], experience_years=8, max_workload=5),
        F.create(Role.TECHNICIAN, "Tom Net", "t2@itsm.local", h, id="U-T2", reports_to="U-LEAD", skills=["NETWORK", "SECURITY"], experience_years=4, max_workload=3),
        F.create(Role.TECHNICIAN, "Tara Gen", "t3@itsm.local", h, id="U-T3", reports_to="U-LEAD", skills=["SOFTWARE", "HARDWARE"], experience_years=2, max_workload=5),
    ]: c.users.add(u)
    for sid, name, crit in [("SVC-PAY", "Payment App", 5), ("SVC-DB", "Database", 4), ("SVC-NET", "Network", 4), ("SVC-MAIL", "Email", 2)]:
        c.db.execute("INSERT INTO services VALUES(?,?,?)", (sid, name, crit))
    for svc, p, r, s in [("*", "P1", 5, 30), ("*", "P2", 15, 120), ("*", "P3", 60, 480), ("*", "P4", 240, 1440),
                         ("SVC-PAY", "P1", 3, 20)]:   # example of a stricter per-service SLA
        c.db.execute("INSERT INTO sla_policies(service_id,priority,response_minutes,resolution_minutes) VALUES(?,?,?,?)", (svc, p, r, s))
    c.config.set("assignment_strategy", "skill")
