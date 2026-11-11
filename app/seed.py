"""Demo data. All passwords: password123."""
from app.domain.enums import Role
from app.domain.models import User, Technician

def seed(c):
    h = c.auth.hash_password("password123")
    c.users.add(User("Admin", "admin@itsm.local", h, Role.ADMIN, id="U-ADMIN"))
    c.users.add(User("Asha Employee", "e1@itsm.local", h, Role.EMPLOYEE, id="U-E1"))
    c.users.add(User("Ravi Employee", "e2@itsm.local", h, Role.EMPLOYEE, id="U-E2"))
    c.users.add(Technician("Tina DB", "t1@itsm.local", h, ["DATABASE", "APPLICATION"], 8, True, 5, id="U-T1"))
    c.users.add(Technician("Tom Net", "t2@itsm.local", h, ["NETWORK", "SECURITY"], 4, True, 3, id="U-T2"))
    c.users.add(Technician("Tara Gen", "t3@itsm.local", h, ["SOFTWARE", "HARDWARE"], 2, True, 5, id="U-T3"))
    for sid, name, crit in [("SVC-PAY", "Payment App", 5), ("SVC-DB", "Database", 4), ("SVC-NET", "Network", 4), ("SVC-MAIL", "Email", 2)]:
        c.db.execute("INSERT INTO services VALUES(?,?,?)", (sid, name, crit))
    for p, r, s in [("P1", 5, 30), ("P2", 15, 120), ("P3", 60, 480), ("P4", 240, 1440)]:
        c.db.execute("INSERT INTO sla_policies VALUES(?,?,?)", (p, r, s))
