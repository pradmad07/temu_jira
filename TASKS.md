# TASKS (for Cline and for humans). Tick `[x]` when done. One task at a time.

State on Nov 15: `pytest` = 73 passed, 0 failed for the current suite.
Completed in this checkpoint: Pradhyumn's P1-P7, notification channels, and IncidentFilter search. Remaining report/UI polish is listed below.
Owners and the original schedule are in docs/PLAN.md. This file is the up-to-date work list.

## Real APIs (use these exact names)
- `container.incident_service`: create_incident(reporter, title, description, category, service_id, impact, urgency, affected_users=1), get_incident(actor, id), list_for(actor), assign_incident(actor, id, technician_id=None), auto_assign(id), change_priority(actor, id, priority, reason), acknowledge(actor, id), start_investigation(actor, id), resolve(actor, id, resolution), verify(actor, id), reject_resolution(actor, id, reason), close(actor, id)
- `container.collab`: add_note(actor, id, text, internal=True), request_info(actor, id, question), reply(actor, id, answer), list_comments(actor, id), submit_feedback(actor, id, rating, comment="")
- `container.admin`: list_categories(), add_category, disable_category, add_service(actor, name, criticality), set_sla_policy(actor, priority, response_minutes, resolution_minutes, service_id="*"), get_assignment_strategy(), set_assignment_strategy(actor, name), create_user(actor, role, name, email, password, reports_to=None, **technician_attrs), set_user_active(actor, user_id, active)
- Repos on container: users, incidents (search(IncidentFilter, limit, offset), count_active_by_technician(id), list_by_assignee(id)), audit (list_all, list_for_incident), services, sla_policies, violations, categories, comments, feedback, config, notifications.
- `container.sla.scan()` (also runs in a background thread every ITSM_SCAN_SECONDS), `container.notification_service`.
- Permissions: Perm.* in app/domain/permissions.py. Technician pages use INCIDENT_VIEW_ASSIGNED / INCIDENT_WORK. Admin pages use ADMIN_REPORTS, ADMIN_AUDIT, ADMIN_CONFIG, ADMIN_USERS.
- Demo logins (password `password123`): e1@itsm.local, t1@itsm.local, lead@itsm.local, admin@itsm.local, mgr@itsm.local.

---
## PRADHYUMN (priority, assignment, intelligence, technician UI)
Files you may edit: app/services/priority.py, assignment.py, duplicates.py, app/web/routes_technician.py, new templates app/web/templates/technician_*.html, new tests.

- [x] **P1 ScoredPriority** (app/services/priority.py). Tests: tests/test_priority.py.
  score = impact x urgency x service.criticality (max 125), optionally boosted when affected_users is large. Map to P1-P4 with named threshold constants (stub suggests >=60 P1, >=30 P2, >=10 P3, else P4). Test cases: 5x5x5 with 500 users -> P1; 1x1x1 -> P4; default helper values (3x3x3 = 27) -> P3 is a good extra test. Write the rationale in the docstring (report needs it).
- [x] **P2 SkillBasedAssignment.choose** (assignment.py). Tests: tests/test_assignment.py.
  Eligible = `t.can_accept(workloads.get(t.id, 0))`. Prefer technicians with `t.has_skill(incident.category)`; deterministic tie-break (lower workload, then more experience, then id). If nobody is eligible raise TechnicianUnavailableError.
- [x] **P3 LoadBasedAssignment.choose**. Eligible as in P2; pick the lowest workload; tie-break by experience then id. Raise TechnicianUnavailableError if none.
- [x] **P4 AssignmentStrategy.recommend** (the base-class method). Returns ranked, explainable recommendations and excludes unavailable/full technicians. Covered by tests/test_recommend.py.
- [x] **P5 DuplicateDetector.find_candidates** (duplicates.py). Tests: tests/test_duplicates.py (2).
  Same service_id, exclude the incident itself, only the `recent_incidents` passed in. Lowercase, drop stopwords, light stemming (so "fails" and "failing" match), Jaccard similarity on word sets. GOTCHA: the stub's default threshold 0.5 is too high for the test pair ("Unable to make payment / payment page fails" vs "Payment application unavailable / payment transactions failing" overlap on only 2 stems). Choose a lower threshold (about 0.2) and document why. Unrelated pair (payment vs printer) must return []. Never delete or merge incidents; return suggestions only.
- [x] **P6 Switch the container to ScoredPriority** (app/container.py). Full suite remains green.
- [ ] **P7 Technician pages** (routes_technician.py + templates). Inbox of `incident_service.list_for(user)` with the technician's active count (`count_active_by_technician`) and max workload; incident detail page (reuse the layout of incident_detail.html); POST routes for acknowledge, start, add note, request info, resolve calling `incident_service` / `collab`. Redirect (303) after each POST. Use `require_permission(Perm.INCIDENT_WORK)` on actions. Show internal notes to staff only (collab.list_comments already hides them from employees).
- [x] **P8 Show suggested duplicates / recommendations in the UI.** Technician detail computes same-service duplicate suggestions and top technician recommendations on the fly without schema changes.
- [x] **P9 Five more tests of your own** (15+ total are required for the report). Added boundary scores, tie-breaks, workload limit, invalid strategy name, and duplicate filtering tests.
- [ ] **P10 Your report section** + screenshots (technician pages, recommendation output).

---
## GAURAV (reports, admin UI, SLA, notifications)
Files you may edit: app/services/reports.py, sla_service.py, notifications.py, app/web/routes_admin.py, new admin templates, new tests.

- [ ] **G1 ReportService** (reports.py): overview() -> dict (total, open, critical, resolved, sla_violations), technician_workload() -> list of (technician name or id, active count), service_counts() -> list of (service name or id, incident count). Currently all three raise NotImplementedError. It only receives `incidents`; if you need users/services/violations, the constructor change touches container.py (Kevalin). Add tests/test_reports.py.
- [ ] **G2 tests/test_search.py** (PLAN lists it, the file does not exist). Verify every field of IncidentFilter is honoured by `search()`: incident_id, status, priority, category, service_id, technician_id, date_from/date_to, text, sla_status (ON_TRACK / AT_RISK / VIOLATED), plus limit/offset. Fix `search()` in sqlite_repos.py if one is missing (tell Kevalin, it is his file).
- [ ] **G3 Admin pages** (routes_admin.py + templates): filterable incident table (IncidentFilter form), reports dashboard (G1), audit log (`audit.list_all`), manage users / services / SLA policies / categories / assignment strategy via `container.admin` (all permission-checked and audited already), and a "Run SLA scan now" button calling `container.sla.scan()`. Admin can assign a technician manually or let the strategy choose (`incident_service.assign_incident(actor, id, technician_id=None)`).
- [ ] **G4 SLA monitor check.** scan() is written; confirm tests/test_sla.py is green, that warnings fire at about 75 percent of the window, that repeated scans do not duplicate events, and that unacknowledged P1 escalation works (uses `reports_to`).
- [ ] **G5 Five more tests** + **report section** (SLA table, notification design: Observer + Adapter) + screenshots.

---
## KEVALIN (domain, integration, employee UI, documents)
Files you may edit: app/domain/*, repositories/*, container.py, schema.sql, auth, app/web/routes_employee.py, employee templates.

- [ ] **K1 Employee pages** (routes_employee.py + incident_detail.html): show non-internal comments (`collab.list_comments`), reply to an information request (`collab.reply`), verify or reject the resolution (`incident_service.verify` / `reject_resolution` with a reason), close, and the 1-5 feedback form (`collab.submit_feedback`). Show buttons only in the matching state; the backend still enforces it.
- [ ] **K2 Review shared-file requests** from P6, P8, G1, G2 and merge them (container.py, interfaces.py, sqlite_repos.py, schema.sql).
- [ ] **K3 Demo data and dry run.** Seed enough users, services and technicians (skills, workload limits) so the three demo workflows work on a clean checkout: (1) employee reports -> prioritised -> auto-assigned -> notified; (2) technician acknowledges -> investigates -> SLA warning -> resolved -> verified -> closed; (3) several similar payment incidents -> duplicates suggested -> unacknowledged P1 escalated.
- [ ] **K4 UML**: use case diagram and class diagram matched to the real code. Document the 15+ test cases (the suite already has 75 tests; pick 15+ and list them with expected results by category).
- [ ] **K5 Report assembly** (PDF): problem analysis, requirements, architecture (docs/DESIGN.md section 1), technology answers (docs/PLAN.md "Stack" + DESIGN section 6), security (docs/SECURITY.md), DB design (schema.sql + ER diagram).

---
## Everyone
- [ ] Nov 15 integration day: full workflow works end to end.
- [ ] Nov 16 feature freeze tonight. Nov 17 tests, screenshots, UML, report draft. Nov 18 clean-checkout run on another laptop, report PDF final.
- [ ] Nov 19-20 record video (15-20 min, each member introduces themselves and explains a module). Nov 21-22 buffer only.
- [ ] Daily 15-minute check-in; report "tests passing: X/Y". Blocked more than 45 minutes: say so.

## Parked (not in the plan, build only if everything above is green)
Admin-defined lifecycle stages, theme/widget builder for dashboards, packet batching for high influx, user "painfulness" rating, mobile/React UI, cloud hosting, ML-based features. Google SSO already exists (routes_sso.py, docs/SSO_AND_HTTPS.md).
