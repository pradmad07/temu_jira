"""Demo data script. Run: python tools/demo_data.py    (Windows: py tools\\demo_data.py)

Builds ~25 incidents over the last 10 days through the real services, so audit
records, SLA deadlines, violations and notifications are genuine.

Database path comes from ITSM_DB (default: itsm.db). Exits if the database
already has incidents — delete the file and re-run to start fresh.
"""
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from anywhere: add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.container import build_container
from app.domain.enums import Priority
from app.domain.filters import IncidentFilter
from app.seed import seed


class SteppingClock:
    """A Clock for demos: advance_to(when) moves time forward to `when`."""
    def __init__(self, start):
        self._now = start

    def now(self):
        return self._now

    def advance_to(self, when):
        if (when - self._now).total_seconds() < -0.001:
            raise ValueError(f"Clock cannot go backwards (now={self._now}, target={when})")
        self._now = when


# Each incident: "created" is minutes-before-now at creation; each step is
# (action, minutes-before-now, *args). Steps for one incident must have strictly
# decreasing min_ago values (later = closer to now).
INCIDENTS = [
    # ───── Closed or verified (12) ─────
    dict(key="db_slow", created=14380, reporter="e1@itsm.local",
         service="SVC-DB", category="DATABASE",
         title="Database queries slow",
         description="Queries on the orders table are 10x slower than yesterday, checkout performance dropping.",
         impact=3, urgency=3, affected=30,
         steps=[
             ("assign", 14360, "t1@itsm.local"),
             ("ack",    14340, "t1@itsm.local"),
             ("start",  14320, "t1@itsm.local"),
             ("resolve", 14280, "t1@itsm.local", "Rebuilt index on orders table, query times back to normal"),
             ("verify",  14180, "e1@itsm.local"),
             ("close",   14080, "e1@itsm.local"),
             ("feedback", 14030, "e1@itsm.local", 5, "Fast turnaround, thanks Tina!"),
         ]),
    dict(key="payment_processing_failing", created=13680, reporter="e1@itsm.local",
         service="SVC-PAY", category="APPLICATION",
         title="Payment processing failing",
         description="All card payments failing since this morning, gateway returning timeouts for every attempt.",
         impact=5, urgency=5, affected=500,
         steps=[
             ("priority", 13677, "P1", "Business critical - all card payments blocked"),
             ("assign",   13676, "t1@itsm.local"),
             ("scan",     13670),  # RESPONSE_VIOLATION + P1_ESCALATION -> lead
             ("ack",      13668, "lead@itsm.local"),
             ("start",    13667, "lead@itsm.local"),
             ("resolve",  13663, "lead@itsm.local", "Payment gateway timeout increased to 30s, traffic stabilised"),
             ("verify",   13610, "e1@itsm.local"),
             ("close",    13510, "e1@itsm.local"),
             ("feedback", 13460, "e1@itsm.local", 4, "Long outage but Tina got it fixed"),
         ]),
    dict(key="network_outage_B", created=12960, reporter="e1@itsm.local",
         service="SVC-NET", category="NETWORK",
         title="Network outage in building B",
         description="All network connectivity lost in building B from 9am, entire floor without service.",
         impact=4, urgency=4, affected=80,
         steps=[
             ("assign", 12940, "t2@itsm.local"),
             ("ack",    12920, "t2@itsm.local"),
             ("start",  12880, "t2@itsm.local"),
             ("resolve", 12720, "t2@itsm.local", "Replaced failing switch in the distribution rack"),
             ("verify",  12600, "e1@itsm.local"),
             ("close",   12480, "e1@itsm.local"),
         ]),
    dict(key="email_delayed", created=12240, reporter="e1@itsm.local",
         service="SVC-MAIL", category="SOFTWARE",
         title="Email delivery delayed",
         description="Emails arriving 2-4 hours late to some recipients, spam filter suspected as the cause.",
         impact=2, urgency=3, affected=200,
         steps=[
             ("assign", 12220, "t3@itsm.local"),
             ("ack",    12200, "t3@itsm.local"),
             ("start",  12160, "t3@itsm.local"),
             ("resolve", 12000, "t3@itsm.local", "Cleared spam queue on the mail relay, delivery back to normal"),
             ("verify",  11880, "e1@itsm.local"),
             ("close",   11760, "e1@itsm.local"),
             ("feedback", 11710, "e1@itsm.local", 5, "Fixed in one afternoon"),
         ]),
    dict(key="db_pool_exhausted", created=11520, reporter="e1@itsm.local",
         service="SVC-DB", category="DATABASE",
         title="Database connection pool exhausted",
         description="Application errors with 'too many connections' during peak hours, users see 500 errors.",
         impact=4, urgency=4, affected=50,
         steps=[
             ("assign", 11500, "t1@itsm.local"),
             ("ack",    11480, "t1@itsm.local"),
             ("start",  11440, "t1@itsm.local"),
             ("resolve", 11280, "t1@itsm.local", "Increased pool size to 100 and added a monitoring alert"),
             ("verify",  11160, "e1@itsm.local"),
             ("feedback", 11110, "e1@itsm.local", 4, "Stable since the fix"),
         ]),
    dict(key="payment_page_slow", created=10080, reporter="e1@itsm.local",
         service="SVC-PAY", category="APPLICATION",
         title="Payment page slow to load",
         description="Payment page taking 10+ seconds to load since last deploy, transactions still succeed.",
         impact=3, urgency=4, affected=120,
         steps=[
             ("priority", 10075, "P1", "Customer-facing slowdown on critical service"),
             ("assign",   10070, "t1@itsm.local"),
             ("ack",      10065, "t1@itsm.local"),
             ("start",    10060, "t1@itsm.local"),
             ("scan",     10055),  # RESOLUTION_VIOLATION only
             ("resolve",  10010, "t1@itsm.local", "Rolled back defective deploy, page loads fast again"),
             ("verify",    9960, "e1@itsm.local"),
             ("close",     9860, "e1@itsm.local"),
         ]),
    dict(key="vpn_home", created=9360, reporter="e1@itsm.local",
         service="SVC-NET", category="NETWORK",
         title="VPN cannot connect from home",
         description="VPN connection refused for all remote workers since this morning, office network unaffected.",
         impact=3, urgency=4, affected=40,
         steps=[
             ("assign", 9340, "t2@itsm.local"),
             ("ack",    9320, "t2@itsm.local"),
             ("start",  9280, "t2@itsm.local"),
             ("resolve", 9120, "t2@itsm.local", "Updated certificate on the VPN gateway, connections restored"),
             ("verify",  9000, "e1@itsm.local"),
             ("close",   8880, "e1@itsm.local"),
         ]),
    dict(key="storage_quota", created=8640, reporter="e1@itsm.local",
         service="SVC-DB", category="STORAGE",
         title="Storage quota exceeded on shared drive",
         description="Shared drive reports quota exceeded, users cannot save new files, edits fail silently.",
         impact=3, urgency=3, affected=60,
         steps=[
             ("assign", 8620, "t3@itsm.local"),
             ("ack",    8600, "t3@itsm.local"),
             ("start",  8560, "t3@itsm.local"),
             ("resolve", 8400, "t3@itsm.local", "Purged stale backups, added 1TB to the volume"),
             ("verify",  8280, "e1@itsm.local"),
             ("close",   8160, "e1@itsm.local"),
         ]),
    dict(key="app_login_slow", created=7200, reporter="e1@itsm.local",
         service="SVC-PAY", category="APPLICATION",
         title="App login slow",
         description="Users waiting 20+ seconds for the app to log them in since the morning, no error messages.",
         impact=2, urgency=3, affected=100,
         steps=[
             ("assign", 7180, "t1@itsm.local"),
             ("ack",    7160, "t1@itsm.local"),
             ("start",  7120, "t1@itsm.local"),
             ("resolve", 6960, "t1@itsm.local", "Rebuilt session cache, logins back under 2 seconds"),
             ("verify",  6840, "e1@itsm.local"),
         ]),
    dict(key="spam_filter_aggressive", created=6480, reporter="e1@itsm.local",
         service="SVC-MAIL", category="SOFTWARE",
         title="Spam filter too aggressive",
         description="Internal emails from colleagues flagged as spam, dozens of false positives reported today.",
         impact=2, urgency=2, affected=80,
         steps=[
             ("assign", 6460, "t3@itsm.local"),
             ("ack",    6440, "t3@itsm.local"),
             ("start",  6400, "t3@itsm.local"),
             ("resolve", 6240, "t3@itsm.local", "Adjusted spam rules for internal domains, false positives gone"),
             ("verify",  6120, "e1@itsm.local"),
             ("close",   6000, "e1@itsm.local"),
             ("feedback", 5950, "e1@itsm.local", 4, "Fixed, no more lost mails"),
         ]),
    dict(key="wifi_drops", created=5040, reporter="e1@itsm.local",
         service="SVC-NET", category="NETWORK",
         title="Wi-Fi drops in conference rooms",
         description="Wi-Fi drops every 10 minutes in conference rooms 2 and 3, wired connections are fine.",
         impact=2, urgency=3, affected=25,
         steps=[
             ("assign", 5020, "t2@itsm.local"),
             ("ack",    5000, "t2@itsm.local"),
             ("start",  4960, "t2@itsm.local"),
             ("resolve", 4800, "t2@itsm.local", "Replaced access point, signal stable since"),
             ("verify",  4680, "e1@itsm.local"),
             ("close",   4560, "e1@itsm.local"),
         ]),
    dict(key="backup_failing", created=4320, reporter="e1@itsm.local",
         service="SVC-DB", category="STORAGE",
         title="Nightly backup failing",
         description="Nightly database backup has been failing for three days, no off-site copies since Monday.",
         impact=4, urgency=3, affected=1,
         steps=[
             ("assign", 4300, "t3@itsm.local"),
             ("ack",    4280, "t3@itsm.local"),
             ("start",  4240, "t3@itsm.local"),
             ("resolve", 4080, "t3@itsm.local", "Cleared stale lockfile and reran backup, off-site copy verified"),
             ("verify",  3960, "e1@itsm.local"),
             ("close",   3840, "e1@itsm.local"),
             ("feedback", 3790, "e1@itsm.local", 4, "Reliable fix, checks passed"),
         ]),

    # ───── Resolved awaiting verification (4) ─────
    dict(key="checkout_500_A", created=3600, reporter="e1@itsm.local",
         service="SVC-PAY", category="APPLICATION",
         title="Payment returns 500 on checkout",
         description="Customers see internal server error 500 after clicking the pay button, all card types affected.",
         impact=4, urgency=4, affected=300,
         steps=[
             ("priority", 3595, "P3", "Triage - duplicate of another report"),  # keep SLA safe
             ("assign",   3580, "t1@itsm.local"),
             ("ack",      3560, "t1@itsm.local"),
             ("start",    3520, "t1@itsm.local"),
             ("resolve",  3360, "t1@itsm.local", "Fixed null pointer in the payment handler, all cards work again"),
         ]),
    dict(key="firewall_block", created=3000, reporter="e1@itsm.local",
         service="SVC-NET", category="NETWORK",
         title="Firewall blocking supplier portal",
         description="Access to the supplier portal blocked since the firewall rule change this morning.",
         impact=3, urgency=3, affected=15,
         steps=[
             ("priority", 2995, "P3", "Triage - awaiting supplier confirmation"),
             ("assign",   2980, "t2@itsm.local"),
             ("ack",      2960, "t2@itsm.local"),
             ("start",    2920, "t2@itsm.local"),
             ("resolve",  2760, "t2@itsm.local", "Added allow rule for supplier portal IPs, access restored"),
         ]),
    dict(key="mailbox_quota", created=2400, reporter="e1@itsm.local",
         service="SVC-MAIL", category="STORAGE",
         title="Mailbox quota exceeded for finance team",
         description="Finance team mailboxes full, cannot receive any external mail since this morning.",
         impact=3, urgency=4, affected=8,
         steps=[
             ("priority", 2395, "P3", "Triage - storage remediation in progress"),
             ("assign",   2380, "t3@itsm.local"),
             ("ack",      2360, "t3@itsm.local"),
             ("start",    2320, "t3@itsm.local"),
             ("resolve",  2160, "t3@itsm.local", "Archived old attachments and increased quota to 50GB"),
         ]),
    dict(key="mobile_ui_slow", created=1800, reporter="e1@itsm.local",
         service="SVC-PAY", category="APPLICATION",
         title="Purchase page load slow on mobile",
         description="Purchase screen slow to load on iPhone devices since yesterday's app update, Android unaffected.",
         impact=2, urgency=3, affected=90,
         steps=[
             ("priority", 1795, "P3", "Triage - awaiting front-end patch"),
             ("assign",   1780, "t1@itsm.local"),
             ("ack",      1760, "t1@itsm.local"),
             ("start",    1720, "t1@itsm.local"),
             ("resolve",  1560, "t1@itsm.local", "Optimised image assets in mobile build, load time under 2s"),
         ]),

    # ───── Assigned / in progress (6) ─────
    dict(key="db_queries_timeout", created=240, reporter="e1@itsm.local",
         service="SVC-DB", category="DATABASE",
         title="Queries timing out after upgrade",
         description="Reports and dashboards timing out after the database upgrade yesterday evening.",
         impact=3, urgency=3, affected=40,
         steps=[
             ("priority", 235, "P3", "Triage - investigating query plans"),
             ("assign",   220, "t1@itsm.local"),
             ("ack",      200, "t1@itsm.local"),
             ("start",    160, "t1@itsm.local"),
         ]),
    dict(key="rack_flapping", created=90, reporter="e1@itsm.local",
         service="SVC-NET", category="NETWORK",
         title="Network flapping in rack 4",
         description="Intermittent packet loss for hosts in rack 4 over the last hour, needs investigation.",
         impact=3, urgency=3, affected=20,
         steps=[
             ("priority", 85, "P3", "Triage - hardware diagnostics in progress"),
             ("assign",   70, "t2@itsm.local"),
             ("ack",      50, "t2@itsm.local"),
         ]),
    dict(key="phishing_filter", created=60, reporter="e1@itsm.local",
         service="SVC-MAIL", category="SOFTWARE",
         title="Phishing emails getting through filter",
         description="Several phishing emails reached user inboxes this morning despite the new filter rules.",
         impact=4, urgency=4, affected=15,
         steps=[
             ("priority", 55, "P3", "Triage - additional filter rules being prepared"),
             ("assign",   40, "t2@itsm.local"),
             ("ack",      30, "t2@itsm.local"),
             ("start",    20, "t2@itsm.local"),
         ]),
    dict(key="dl_not_receiving", created=45, reporter="e1@itsm.local",
         service="SVC-MAIL", category="SOFTWARE",
         title="Distribution list not receiving mail",
         description="Project distribution list not delivering messages for the past two hours, needs review.",
         impact=2, urgency=3, affected=30,
         steps=[
             ("priority", 40, "P4", "Triage - lower priority than the payment incident"),
             ("assign",   25, "t3@itsm.local"),
         ]),
    dict(key="checkout_500_C", created=90, reporter="e1@itsm.local",
         service="SVC-PAY", category="APPLICATION",
         title="Checkout returns 500 for payment",
         description="Pay action fails with 500 internal server error for all customers during checkout.",
         impact=4, urgency=4, affected=400,
         steps=[
             ("priority", 85, "P2", "Triage - investigating alongside the other payment reports"),
             ("assign",   70, "t1@itsm.local"),
             ("ack",      50, "t1@itsm.local"),
             ("start",    30, "t1@itsm.local"),
         ]),
    dict(key="storage_full_recurring", created=60, reporter="e1@itsm.local",
         service="SVC-DB", category="STORAGE",
         title="Database disk filling up again",
         description="Database volume at 92% again after the cleanup last week, needs a longer-term fix.",
         impact=3, urgency=4, affected=10,
         steps=[
             ("priority", 55, "P2", "Triage - capacity planning needed"),
             ("assign",   45, "t1@itsm.local"),
             ("ack",      30, "t1@itsm.local"),
             ("start",    15, "t1@itsm.local"),
         ]),

    # ───── New / classified (3) ─────
    dict(key="checkout_500_B", created=5, reporter="e1@itsm.local",
         service="SVC-PAY", category="APPLICATION",
         title="Payment failing with 500",
         description="Users see internal server error 500 when paying, all cards affected, still ongoing.",
         impact=4, urgency=4, affected=300,
         steps=[
             ("priority", 4, "P2", "Triage - queueing for the payment team"),
         ]),
    dict(key="reports_slow", created=50, reporter="e1@itsm.local",
         service="SVC-DB", category="DATABASE",
         title="Reports slow this afternoon",
         description="Finance reports taking several minutes to load, one request timed out for a user.",
         impact=2, urgency=2, affected=5,
         steps=[
             ("priority", 45, "P3", "Triage - scheduled alongside the upgrade follow-up"),
         ]),  # 50-min-old P3 SVC-DB -> 83% of 60-min response window -> WARNING on live scan
    dict(key="laptop_battery", created=120, reporter="e1@itsm.local",
         service="SVC-NET", category="HARDWARE",
         title="Laptop battery not charging",
         description="Laptop battery not charging when plugged in, amber LED blinking instead of solid.",
         impact=1, urgency=2, affected=1,
         steps=[]),
]


def _run_step(c, inc_id, action, args):
    admin = c.users.get_by_email("admin@itsm.local")
    if action == "scan":
        c.sla.scan()
    elif action == "assign":
        target = c.users.get_by_email(args[0])
        c.incident_service.assign_incident(admin, inc_id, target.id)
    elif action == "ack":
        c.incident_service.acknowledge(c.users.get_by_email(args[0]), inc_id)
    elif action == "start":
        c.incident_service.start_investigation(c.users.get_by_email(args[0]), inc_id)
    elif action == "resolve":
        c.incident_service.resolve(c.users.get_by_email(args[0]), inc_id, args[1])
    elif action == "verify":
        c.incident_service.verify(c.users.get_by_email(args[0]), inc_id)
    elif action == "close":
        c.incident_service.close(c.users.get_by_email(args[0]), inc_id)
    elif action == "feedback":
        comment = args[2] if len(args) > 2 else ""
        c.collab.submit_feedback(c.users.get_by_email(args[0]), inc_id, int(args[1]), comment)
    elif action == "priority":
        c.incident_service.change_priority(admin, inc_id, Priority[args[0]], args[1])
    else:
        raise ValueError(f"Unknown action: {action}")


def main():
    db_path = os.environ.get("ITSM_DB", "itsm.db")
    end_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start_time = end_time - timedelta(days=10)

    clock = SteppingClock(start=start_time)
    c = build_container(db_path=db_path, clock=clock, auto_assign=False)

    if len(c.incidents.search(IncidentFilter(), limit=1)) > 0:
        print(f"Database '{db_path}' already contains incidents.")
        print("Delete the file and re-run this script to populate a fresh demo.")
        sys.exit(1)

    if not c.users.get_by_email("admin@itsm.local"):
        seed(c)
        print(f"Seeded users, services, categories and SLA policies into '{db_path}'.")
    else:
        print(f"Using existing seed data in '{db_path}'.")

    # Flatten every incident's timeline into one sorted event list (oldest first)
    spec_by_key = {i["key"]: i for i in INCIDENTS}
    events = []
    for inc in INCIDENTS:
        events.append((inc["created"], inc["key"], "create", ()))
        for step in inc["steps"]:
            action, min_ago, *args = step
            events.append((min_ago, inc["key"], action, tuple(args)))
    events.sort(key=lambda e: (-e[0], e[1]))  # larger min_ago = older = first

    created = {}
    for min_ago, key, action, args in events:
        try:
            clock.advance_to(end_time - timedelta(minutes=min_ago))
            if action == "create":
                spec = spec_by_key[key]
                reporter = c.users.get_by_email(spec["reporter"])
                inc = c.incident_service.create_incident(
                    reporter,
                    spec["title"],
                    spec["description"],
                    spec["category"],
                    spec["service"],
                    spec["impact"],
                    spec["urgency"],
                    spec["affected"],
                )
                created[key] = inc
            else:
                _run_step(c, created[key].id, action, args)
        except Exception as e:
            print(f"\nFAILED at {action} for '{key}' (min_ago={min_ago}): {e}")
            raise

    # Land the clock at real "now" so the newest open incidents look fresh
    clock.advance_to(datetime.now(timezone.utc))

    # Summary
    all_incidents = c.incidents.search(IncidentFilter(), limit=500)
    status_counts = Counter(i.status.value for i in all_incidents)
    total_notifs = sum(len(c.notifications.list_for_recipient(u.id)) for u in c.users.list_all())
    total_audit = len(c.audit.list_all(limit=10000))
    total_violations = (
        c.violations.count_violated_incidents() if hasattr(c.violations, "count_violated_incidents")
        else len(set(r[0] for r in c.violations.list_all()))
    )

    print()
    print("=== Demo data created ===")
    print(f"Database:               {db_path}")
    print(f"Incidents:              {len(all_incidents)}")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<22}{count}")
    print(f"SLA violations (distinct incidents): {total_violations}")
    print(f"Notifications:          {total_notifs}")
    print(f"Audit records:          {total_audit}")
    print()
    print("Demo logins (password 'password123'):")
    print("  admin@itsm.local    - admin dashboard")
    print("  lead@itsm.local     - team lead, technician inbox")
    print("  t1@itsm.local       - technician (Tina, DATABASE/APPLICATION)")
    print("  e1@itsm.local       - employee who reported most incidents")
    print()
    print("Tip: log in as admin and click 'Run SLA scan' to see a warning fire on the")
    print("     most recent P3 incident ('Reports slow this afternoon').")


if __name__ == "__main__":
    main()
