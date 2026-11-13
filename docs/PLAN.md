# Plan (re-baselined Nov 11). Internal "submission ready" = Nov 18. Hard deadline = Nov 22.

## Stack (and why - needed for the report's 9 questions)
Python 3 + FastAPI + Jinja2/Bootstrap (server-rendered, no separate frontend) + SQLite via stdlib `sqlite3` behind Repository interfaces.
Why not React/Mongo: no build toolchain or DB server to install on 3 laptops; data is relational (joins for workload/reports); repositories mean we can swap DB later.

## Java -> Python cheat sheet
interface -> `abc.ABC` + `@abstractmethod` | private field -> `self._x` + `@property` | enum -> `Enum` | `extends` -> `class B(A)`
`throws` -> `raise` + custom exceptions in `domain/exceptions.py` | `ArrayList/HashMap` -> `list/dict` | `Optional` -> `None` | constructor -> `__init__`

## Architecture rules (these are what get marked)
- Layers: `web` (HTTP only) -> `services` (use cases) -> `domain` (rules) -> `repositories` (SQL). Never skip a layer, never put SQL in services.
- Patterns we are claiming, with where they live: **Strategy** (priority.py, assignment.py), **Observer** (events.py, audit.py, notifications.py),
  **State** (states.py), **Repository** (repositories/), **Adapter** (notification channels). Don't claim others.
- The logged-in user comes from the session, never from a form field. Backend checks permission on every action.
- Don't edit another person's files without telling them. Shared files (domain/, schema.sql, container.py) go through Kevalin.

## Owners (every one of you must explain your part in the video)
| Person | Owns | Done when these tests pass |
|---|---|---|
| Kevalin | domain, repos, auth, integration. Lifecycle use cases are DONE (read `incident_service.py` first: it is the pattern for everything). Remaining: employee pages for reply / verify / reject / feedback | test_lifecycle_service, test_incident_service, test_states, test_auth (all green now) |
| Pradhyumn | priority.py, assignment.py (2 strategies + `recommend()`), duplicates.py, technician pages (call `incident_service` + `collab`, both exist). Then switch `container.py` to `ScoredPriority()` | test_priority, test_assignment, test_duplicates |
| Gaurav | `SlaService.scan()` (`deadlines_for` is DONE), notifications.py (2 channels), reports.py, `search()` with `IncidentFilter`, admin pages (call `AdminService`, it exists) | test_sla, test_notifications, test_search |

Each person also: adds 5 more tests of their own (15+ total required), writes their own report section, takes screenshots.
Intelligent features: (1) technician recommendation (2) duplicate detection. Extra if all green by Nov 16: auto-escalation of unacknowledged P1 (inside `SlaService.scan`).

## Schedule
| Date | Goal |
|---|---|
| Nov 11 | Everyone runs the app + pytest. Read your files. Pradhyumn: write priority thresholds + assignment rules on paper. Gaurav: use-case diagram + SLA table. Kevalin: assign/acknowledge/start/resolve use cases. |
| Nov 12 | First merged change from EACH person. Employee flow demo-able. |
| Nov 13-14 | Own modules: strategies + technician page | SLA + notifications + admin filters | lifecycle use cases + employee verify/feedback. |
| Nov 15 | Integration day. Full workflow: report -> prioritise -> assign -> notify -> acknowledge -> resolve -> verify -> close. |
| Nov 16 | Fix bugs. Optional escalation. Feature freeze tonight. |
| Nov 17 | 15+ documented tests, screenshots, UML (use case + class) matched to real code, report draft complete. |
| Nov 18 | Clean-checkout run on another laptop, 3 workflows rehearsed, report PDF final. |
| Nov 19-20 | Record video (all three, 15-20 min, each introduces self and explains a module). Upload. |
| Nov 21-22 | Buffer only. Filename per brief: `<GroupNo>_OOP_S1_2025-2026_Project` (brief says 2025-26 - ask instructor). |

## Habits
15-min check-in daily; report "tests passing: X/20". Blocked > 45 min = say so. Small commits daily.
Fallback: if a module has nothing merged by Nov 13 night, Kevalin writes a simple version and scope shrinks.

## Cut list (do NOT build): SSO, admin-defined lifecycle stages, theme/widget builder, packet batching, "painfulness" ratings, React, cloud hosting, ML.
Fuzzy search = simple text match. AI = optional; rule-based is explicitly acceptable.

## Design, scaling and known gaps
See docs/DESIGN.md (requirement traceability, patterns, scaling path, known gaps) and docs/SECURITY.md.
