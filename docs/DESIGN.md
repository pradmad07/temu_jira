# Design, traceability and scaling notes (reuse in the report)

## 1. Architecture in one picture
```
 browser --> web/ (routes + templates: HTTP only)
               |  uses
            services/  IncidentService | CollaborationService | AdminService | AuthService | SlaService ...
               |  uses                         ^ publish events
            domain/    Incident, User, Technician, states, events, permissions, exceptions   (no DB, no HTTP)
               |  persisted through
            repositories/  interfaces.py  <--  sqlite_repos.py      --> SQLite file
 EventBus (Observer): audit, notifications, auto-assign subscribe; services never call them directly.
```
`container.py` wires everything once (manual dependency injection). Tests build the same container with a fake clock.

## 2. Brief requirement -> where it lives -> status
| Brief item | Code | Status |
|---|---|---|
| Employee / Technician / Admin (+ team lead, IT manager) | `domain/enums.Role`, `permissions.py` | done |
| Admin manages users, services, SLA, categories, strategy | `AdminService` (permission-checked, audited) | services done; **pages: Gaurav** |
| Incident create / view / update / assign / resolve / close | `IncidentService` | done; employee verify/reply/feedback pages: **Kevalin**; technician pages: **Pradhyumn** |
| Priority from impact, urgency, criticality | `PriorityStrategy`; `Incident` + `Service.criticality` | interface done; `ScoredPriority`: **Pradhyumn** |
| >= 2 assignment strategies, changeable without redesign | `assignment.py` registry + `config` table + `AutoAssigner` + admin switch | plumbing done; two strategies: **Pradhyumn** |
| SLA calculation, per-service, deadline snapshot | `SlaService.deadlines_for`, `sla_policies(service_id, priority)`, `Incident.sla` | done |
| SLA warnings, violation detection | `SlaService.scan`, `sla_violations`, background `PeriodicTask` | thread + dedupe done; `scan()`: **Gaurav** |
| >= 2 notification mechanisms | `NotificationChannel` (Adapter) + Observer | skeleton; **Gaurav** |
| Audit: who, what, when, old/new state | `AuditObserver`, `audit_records` (incl. admin actions) | done; admin log page: **Gaurav** |
| >= 5 search filters, dashboards | `IncidentFilter`, `search()`, `ReportService` | contract done; **Gaurav** |
| >= 2 intelligent features | `recommend()`, `DuplicateDetector` | stubs; **Pradhyumn** |
| Lifecycle with illegal transitions blocked | `domain/states.py` (State pattern) | done, tested |
| Persistence | repositories + SQLite | done |
| Exceptions from the brief | `ValidationError`, `AuthenticationError`, `AuthorizationError`, `NotFoundError` (invalid incident, service not found), `InvalidTransitionError`, `TechnicianUnavailableError`, `WorkloadExceededError`, `MissingSlaError`, `PersistenceError`, `ExternalServiceError` (for notification/AI adapters); `DuplicateIncidentError` exists but duplicates are only *suggested*, never blocked | done / mapped to HTTP codes in `main.py` |
| Security | see docs/SECURITY.md | basics done |

## 3. OOP concepts -> evidence
Encapsulation: private fields + properties (`User`, `Incident`). Abstraction: use-case methods hide rules. Inheritance: `Technician(User)`, exception hierarchy, concrete states and strategies. Polymorphism: states, strategies, channels, repositories are interchangeable behind one interface. Interfaces: ABCs in `interfaces.py`, `PriorityStrategy`, `AssignmentStrategy`, `NotificationChannel`. Composition: `Incident` owns its state object and `SlaDeadlines`; services are composed from repositories. Collections: `dict` registry/permissions, `frozenset` skills and permissions, NamedTuple.

## 4. Patterns (claim only these)
Strategy (priority, assignment), Observer (EventBus: audit, auto-assign, notifications), State (lifecycle), Repository (all persistence), Factory (`UserFactory`), Adapter (notification channels, and the future AI client).

## 5. Decisions worth defending
- **State pattern for the lifecycle.** An incident has no status field, only a state object, so an illegal move is impossible rather than checked. Adding `reassign` took 3 one-line methods.
- **Events decouple side effects.** Creating an incident publishes two events; audit, auto-assignment and (later) notifications react. `auto_assign=False` removes a behaviour without touching any other class.
- **SLA is a snapshot on the incident** (`response_due`, `resolution_due`). Editing a policy never rewrites history, and "what is overdue?" is a cheap query. Changing priority recomputes it and is audited.
- **Active strategy is data.** Registry (code) says which strategies *exist*; the config table says which is *active*. New strategy = one class + one registry line (proved in `test_assignment_flow.py`).
- **Per-service SLA** with a `'*'` default: the brief says services may differ.
- **Roles are a permission map**, not scattered `if role ==`. `can_view_incident` is the single read rule.
- **Other aggregates are referenced by ID** (`reporter_id`, `service_id`, `assigned_to`), a deliberate aggregate-boundary choice. Be ready to explain it: the UML shows these as associations, and real object collaboration happens in the services and strategies (`choose(incident, technicians, workloads)`). If a marker wants object references, add a read model that hydrates them; it would not change the domain.
- **SQLite + stdlib `sqlite3`**: zero setup, relational data, behind repository interfaces.

## 6. Scaling path (report question 9)
1. Database: write Postgres/MySQL repositories behind the same interfaces; change `sqlite_repos.py` and `schema.sql` syntax only.
2. Web tier: sessions live in a signed cookie, so web workers are stateless and can be added behind a load balancer.
3. Background work: the SLA scan is idempotent (`INSERT OR IGNORE` on `sla_violations`), so several workers scanning is safe; move it to a worker process/queue when needed.
4. Events: the in-process `EventBus` can be replaced by a message queue; publishers do not change.
5. Reads: indexes exist on status, assignee, reporter, due date; `search()` is paginated by contract.
6. Writes: commit-per-statement today; a Unit of Work (one commit per use case) is the next step.

## 7. Known gaps (be honest in the report)
Pages for technician, admin, and employee reply/verify/feedback; `search()`; notifications; scan(); intelligent features; times are shown in UTC (timezone per user is an extension); no DB migrations (delete `itsm.db` after schema changes); incident + audit are separate commits; `incident_links` has no repository yet (duplicate/correlation storage); no rate limiting or CSRF tokens (see SECURITY.md).
