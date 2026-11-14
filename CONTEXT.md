# Project Context: Temu Jira

## Current Focus
**Pradhyumn Workstream:** Assignment Strategies, Duplicate Detection & Technician UI.

## Current Task
Complete the Pradhyumn workstream and restore a green test suite.

## Technical Plan
- **File:** `app/services/assignment.py`
- **Approach:**
    - Add a private `_get_eligible_candidates` method to the `AssignmentStrategy` base class to filter technicians based on `can_accept()`.
    - **SkillBasedAssignment:**
        - Use the helper to get eligible candidates.
        - Sort by `has_skill` (True first), then `workload` (lower first), then `experience` (higher first), then `id`.
    - **LoadBasedAssignment:**
        - Use the helper to get eligible candidates.
        - Sort by `workload` (lower first), then `experience` (higher first), then `id`.
- **Completed:** P1-P7 are implemented; recommendation, duplicate detection, scored priority wiring, technician routes/templates, notification delivery, and repository search now have coverage.
- **Validation:** `pytest -q` => 73 passed.

## References
- **Domain Model:** `app/domain/models.py` (Technician properties: `has_skill`, `can_accept`, `experience_years`)
- **Existing Tests:** `tests/test_assignment.py`
- **Requirement Traceability:** `docs/DESIGN.md`

## Blockers/Notes
- P8 duplicate/recommendation display and P9 additional edge-case tests are complete.
- P10 report section and screenshots remain a manual deliverable.
- Do not commit the supplied PDFs or image; they are project inputs, not application source.
