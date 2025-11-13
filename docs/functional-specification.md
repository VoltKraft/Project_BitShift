# Project BitShift — Functional Specification (FS)

Product name: Chronos — Intelligent Shift and Leave Planning System

Status: Draft  
Version: 0.1  
Last Updated: 2025-11-12

## Contents

- 1. Overview
- 2. Architecture Overview
- 3. Requirement-to-Design Mapping
- 4. Detailed Flows
- 5. Data Model
- 6. Interfaces
- 7. Quality Attributes and NFRs
  - 7.1 Compliance & Security
- 8. Deployment & Operations
- 9. Open Issues
- 10. Traceability
  - 10.1 Requirements Traceability Matrix

This specification translates the Customer Requirements Specification (CRS) into a solution design suitable for implementation and testing. It provides architecture, components, data models, interfaces, security, quality attributes, and requirement-to-design traceability.

## 1. Overview

- Problem statement: Manual, opaque, error-prone Excel-based planning and paper-based approvals.
- Solution approach: Web-based, modular planning system with automated scheduling, digital approvals, and integrations; Linux-first, open source.
- Scope confirmation: Aligns with CRS sections 3–8; defers non-goals to CRS if any.

## 2. Architecture Overview

- Runtime: Linux servers; containerized services (Docker); optional orchestration (Kubernetes).
- Style: Service-oriented (microservices where justified) with clear module boundaries.
- Core services (initial cut):
  - Identity & Access (RBAC, OAuth2/SSO integration)
  - User & Org (users, teams, departments)
  - Leave Service (requests, approvals, delegation)
  - Scheduling Engine (shift rules, preferences, constraints)
  - Notifications (SMTP, push/webhook dispatch)
  - Reporting & Analytics (read models, exports)
  - API Gateway/Edge (REST/GraphQL, rate limits, versioning)
- Data: PostgreSQL as primary store; schema per service; migrations versioned.
- Observability: Prometheus metrics, structured logs, Grafana dashboards.

## 3. Requirement-to-Design Mapping (excerpt)

- F1 User management → Identity & Access, User & Org services; RBAC model.
- F2 Leave management → Leave Service (CRUD, state machine, SLAs).
- F3 Delegate search → Leave Service + scheduling constraints (availability, skills, workload).
- F4 Approval workflow → Leave Service workflow engine (Employee → Delegate → Team Lead → HR).
- F5 Shift planning → Scheduling Engine (rules, preferences, fairness; pluggable solver for AI/optimization).
- F6 Preferences → User profile + Scheduling Engine inputs.
- F7 External factors → Calendars/holidays, projects, service hours as constraints in Scheduling Engine.
- F8 Notifications → Notifications service (SMTP, optional push/webhooks; templating).
- F9 Reporting → Reporting service (materialized views; CSV/Excel/PDF exports).
- F10 Interfaces/API → API Gateway; REST/GraphQL surface; OpenAPI/SDL definitions.
- F11 Calendar integration → ICS exports; optional CalDAV adapter.
- F12 Roles & permissions → RBAC policies enforced at gateway and service level.

## 4. Detailed Flows (high level)

- Leave request (Employee): create → select dates → auto-delegate proposal → submit → approvals → notify.
- Shift plan generation (Planner/Team lead): define horizon → import constraints (holidays, projects) → run solver → review conflicts → publish.
- Approval workflow: stage transitions with SLAs and reminders; override/escalation paths.

## 5. Data Model (initial)

- Key entities: User, Team, Department, Shift, ShiftAssignment, LeaveRequest, Delegate, Project, CalendarEvent, Preference.
- Integrity: relational constraints, validations; audit fields; soft delete where needed.

### 5.1 Entity Catalog (skeleton)

Entity | Key Attributes | Relationships | Notes
--- | --- | --- | ---
User | id (UUID, PK); email (unique, not null); first_name; last_name; locale; time_zone; role; department_id (FK); team_id (FK); created_at; updated_at; deleted_at | 1:N Department → User; 1:N Team → User | Unique: email; FKs: department_id → Department(id) ON SET NULL, team_id → Team(id) ON SET NULL; Index: (department_id), (team_id), (email); Soft-delete via deleted_at
Team | id (UUID, PK); name (unique per department); department_id (FK); created_at; updated_at; deleted_at | 1:N Team → User; N:1 Team → Department | Unique: (department_id, name); FK: department_id → Department(id) ON CASCADE UPDATE/RESTRICT DELETE; Index: (department_id)
Department | id (UUID, PK); name (unique); created_at; updated_at; deleted_at | 1:N Department → Team; 1:N Department → User | Unique: name; Index: (name)
Project | id (UUID, PK); code (unique); name; created_at; updated_at; deleted_at | 1:N Project → Shift | Unique: code; Index: (code)
Shift | id (UUID, PK); service_date (date); shift_type (enum: EARLY,LATE,OTHER); start_time; end_time; team_id (FK); project_id (FK, nullable); created_at; updated_at; deleted_at | N:1 Shift → Team; N:1 Shift → Project; 1:N Shift → ShiftAssignment | Unique: (team_id, service_date, shift_type); FKs: team_id → Team(id) ON CASCADE; project_id → Project(id) ON SET NULL; Index: (service_date), (team_id, service_date)
ShiftAssignment | id (UUID, PK); shift_id (FK); user_id (FK); assigned_at; created_at; updated_at; deleted_at | N:1 ShiftAssignment → Shift; N:1 ShiftAssignment → User | Unique: (shift_id, user_id); FKs: shift_id → Shift(id) ON CASCADE; user_id → User(id) ON RESTRICT; Index: (shift_id), (user_id)
LeaveRequest | id (UUID, PK); requester_id (FK User); approver_delegate_id (FK User, nullable); approver_tl_id (FK User, nullable); approver_hr_id (FK User, nullable); type (enum: VACATION,SICK,OTHER); reason (text, nullable); start_date; end_date; status (state: DRAFT,SUBMITTED,DELEGATE_REVIEW,TL_REVIEW,HR_REVIEW,APPROVED,REJECTED,CANCELLED,OVERRIDDEN); submitted_at; decided_at; created_at; updated_at; deleted_at | N:1 → User (requester/approvers); 1:N LeaveRequest → CalendarEvent (derived) | Constraints: start_date ≤ end_date; no overlap per requester and type when status ∈ {SUBMITTED..APPROVED}; FK actions: requester_id ON RESTRICT; approver_* ON SET NULL; Index: (requester_id), (start_date), (status); Partition: by year on start_date (range)
Delegate | id (UUID, PK); principal_id (FK User); delegate_user_id (FK User); valid_from; valid_to; created_at; updated_at; deleted_at | N:1 → User (principal); N:1 → User (delegate) | Unique: (principal_id, delegate_user_id, valid_from, valid_to); FK actions: ON CASCADE UPDATE/RESTRICT DELETE; Index: (principal_id), (delegate_user_id), (valid_from, valid_to)
CalendarEvent | id (UUID, PK); user_id (FK); event_type (enum: HOLIDAY,LEAVE,SHIFT,OTHER); starts_at; ends_at; source (enum: SYSTEM,EXTERNAL); external_ref (nullable); created_at; updated_at; deleted_at | N:1 → User; Optional link to LeaveRequest or Shift | Index: (user_id), (starts_at), (event_type); Partition: by month on starts_at (range)
Preference | id (UUID, PK); user_id (FK); preference_type (enum: SHIFT_TIME,DAY_OFF,PROJECT); payload (JSONB); effective_from; effective_to; created_at; updated_at; deleted_at | N:1 → User | Unique: (user_id, preference_type, effective_from); Index: (user_id), GIN (payload)

Partitioning & Archival Strategy:

- High-volume tables (LeaveRequest by year on start_date; CalendarEvent by month on starts_at) are partitioned to improve query and retention operations.
- Archival: finalized LeaveRequest and related CalendarEvent older than configurable retention (e.g., 24 months) are moved to archive schema/tables; indexes preserved for export/reporting; PII is minimized or pseudonymized per §7.1.
- Foreign keys from partitions reference parent tables via partition-aware constraints.

## 6. Interfaces

- REST/GraphQL for frontend and integrations; versioned; standard error model.
- LDAP/SSO (OAuth2/OpenID Connect) for authentication; roles mapped to claims.
- SMTP for email; templated messages.
- ICS/CalDAV (optional) for calendar sync; ICS export baseline.
- Webhooks for external triggers and automations.

## 7. Quality Attributes and NFRs

- Performance: ≤ 2 s P95 at 100 concurrent users (typical flows).
- Availability: 99% (normal operations); health checks; graceful degradation.
- Security: TLS everywhere; least-privilege RBAC; GDPR compliance; encrypted secrets.
- Scalability: horizontal scale via containers; stateless services where possible.
- Testability: unit/integration/E2E tests; CI/CD pipeline; seed data for staging.
- Maintainability: modular codebases; clear service contracts; API versioning.

### 7.1 Compliance & Security

The system must implement the following compliance and privacy controls. References: GDPR (esp. Arts. 5, 6, 7, 17, 20, 25, 30, 32), CCPA where applicable.

1) Immutable Audit Trail (approvals/rejections/overrides/config changes)
- Must record append-only audit events for: leave approvals/rejections, workflow overrides, role/permission changes, configuration changes (e.g., shift rules), and data exports/deletions.
- Each event must capture: actor (user id and role), timestamp (UTC), action type, reason/comment (if provided), target entity and id, and before_state/after_state (JSON snapshots with minimal necessary fields; exclude secrets/PII not needed for audit).
- Storage must be tamper-evident: either WORM storage, cryptographic hash chaining per event, or database-level immutability controls. Events are not updatable or deletable by application code; redaction is handled via separate redaction records linked to the event.
- Access must be RBAC-restricted; search/filter by actor, action, date range; export to CSV/JSON for compliance review.
- Retention must be configurable per organization and data category; defaults: 24 months for operational audit; longer if required by law/policy.
- Acceptance criteria:
  - Triggering each workflow action (approve/reject/override/config change) creates an audit event with all required fields.
  - Attempted update/delete of an audit event is rejected and logged.
  - Hash chain validation detects any tampering in a sample audit log.
  - Authorized roles can query and export filtered audit logs; unauthorized roles are denied.

2) User Data Export (GDPR Art. 20 — portability)
- Must provide user-initiated export of their personal data: identity profile (PII), leave history, preferences, and calendar items derived from their data.
- Export formats: machine-readable JSON (authoritative) and CSV for tabular data; ICS for calendar events. Exports must include schema version and generation timestamp.
- Export delivery: asynchronous job with signed, time-limited download URL; notify user on completion.
- SLA: export must be available within 30 days of request (configurable; typically minutes for standard volumes).
- Acceptance criteria:
  - API `POST /api/v1/users/{id}/export` enqueues an export; `GET /api/v1/users/{id}/export/{job_id}` returns status and download link when ready.
  - Export contains expected records and fields for a test user; checksums included.
  - Access to another user’s export is denied; links expire as configured.

3) User Data Deletion/Termination (GDPR Art. 17 — erasure)
- Must support account termination workflow: deactivate user (immediate login block), schedule deletion of personal data after configurable retention (default: 30 days cooling-off, then erase); maintain minimal legally required records.
- Deletion scope: PII in User, Preferences, and personal CalendarEvents. LeaveRequest and ShiftAssignment may be retained in aggregated or pseudonymized form to preserve operational history; direct identifiers must be removed or replaced.
- Referential behavior: FK references to deleted users must be set to NULL or replaced by pseudonymous keys; audit trail remains immutable but may be logically restricted by access policies.
- A deletion ledger must record request time, executor, scope, outcome, and items affected.
- Acceptance criteria:
  - API `POST /api/v1/users/{id}/erase` initiates deletion; status endpoint reports progress/outcome.
  - After deletion, PII fields are removed/pseudonymized; attempts to retrieve profile data return not found or redacted.
  - References in LeaveRequest and ShiftAssignment are NULL/pseudonymous; reporting still functions on aggregates.

4) PII Attributes, Purpose, Minimization, and Consent
- Required PII attributes: first_name, last_name, email, (optional) phone; organizational attributes: department_id, team_id, role. Do not store sensitive categories unless strictly necessary and justified.
- Purpose limitation: collect only attributes necessary for scheduling, approvals, notifications, and access control. No unrelated processing.
- Minimization rules: default to opt-in for optional features (e.g., push notifications, external calendar sharing); avoid free-form PII where structured fields suffice.
- Consent capture: consent statements must be explicit, versioned, and displayed at the point of collection; changes (grant/withdraw) must be logged as audit events with actor, timestamp, policy version, and scope.
- Data protection by design: default privacy settings conservative; configuration for retention, export, and deletion documented and testable.
- Acceptance criteria:
  - Consent change produces an audit event; current consent state is reflected in user profile and enforced by services.
  - Attempting to process data beyond stated purposes is blocked by policy checks (simulated in tests).
  - PII fields are present only where required; redaction appears in logs/exports as specified.

## 8. Deployment & Operations

- Dev: Docker Compose; Prod: Helm (optional); env vars for config; secrets via vault/K8s secrets.
- Backups: daily automated Postgres backups; restore drill documented (RPO/RTO).
- Monitoring: Prometheus metrics, Grafana dashboards; structured logs; alerting.

## 9. Open Issues

- Select optimization approach (rule-based, MILP/CP-SAT, or hybrid) for Scheduling Engine.
- Push notifications mechanism (web push vs. mobile app) — scope decision.
- CalDAV support depth vs. ICS-only for v1.

## 10. Traceability

Map CRS features (F1–F12) to components, APIs, and test cases. Maintain a matrix linking CRS → FS sections → Test IDs.

### 10.1 Requirements Traceability Matrix

Source of truth: Spreadsheet (to be created) at https://example.com/bitshift/traceability. The matrix below is mirrored in docs and must be updated in the same commit as related code/tests. Process: for any change to features, APIs, or ownership, update this table, update OpenAPI/SDL, and add/adjust tests with matching Test Case IDs.

| CRS Feature | FS Section | Component(s) | API Endpoint(s) | Test Case ID | Owner |
|---|---|---|---|---|---|
| F1 User management | §§3, 5.1, 6, 7.1 | Identity & Access; User & Org | GET/POST/PUT/DELETE /api/v1/users; GET/POST /api/v1/roles | TC-F1-001 | IAM Team |
| F2 Leave management | §§3, 4, 5.1, 6, 7.1 | Leave Service | GET/POST /api/v1/leaves; GET /api/v1/leaves/{id}; PATCH /api/v1/leaves/{id} | TC-F2-001 | Leave Team |
| F3 Delegate search | §§3, 4, 5.1, 6 | Leave Service; Scheduling Engine | GET /api/v1/leaves/{id}/delegate-suggestions | TC-F3-001 | Leave Team |
| F4 Approval workflow | §§3, 4, 5.1, 6, 7.1 | Leave Service | POST /api/v1/leaves/{id}/approve; POST /api/v1/leaves/{id}/reject; POST /api/v1/leaves/{id}/override | TC-F4-001 | Leave Team |
| F5 Shift planning | §§3, 4, 5.1, 6 | Scheduling Engine | POST /api/v1/schedule/generate; GET /api/v1/schedule/plans | TC-F5-001 | Scheduling Team |
| F6 Preferences | §§3, 5.1, 6, 7.1 | User & Org; Scheduling Engine | GET/PUT /api/v1/preferences; GET /api/v1/users/{id}/preferences | TC-F6-001 | IAM Team |
| F7 External factors | §§3, 4, 5.1, 6 | Scheduling Engine; Integrations | GET/POST /api/v1/calendar/events; POST /api/v1/calendar/import-holidays; GET /api/v1/projects | TC-F7-001 | Integrations Team |
| F8 Notifications | §§3, 4, 6 | Notifications | POST /api/v1/notifications/preview; N/A (internal dispatch) | TC-F8-001 | Notifications Team |
| F9 Reporting | §§3, 5.1, 6 | Reporting & Analytics | GET /api/v1/reports/leave; GET /api/v1/reports/utilization; GET /api/v1/exports | TC-F9-001 | Reporting Team |
| F10 Interfaces/API | §§2, 3, 6 | API Gateway/Edge | GET /api/v1/openapi; GraphQL /api/graphql | TC-F10-001 | Gateway Team |
| F11 Calendar integration | §§3, 6 | Integrations | GET /api/v1/calendar/ics; CalDAV N/A (v1 optional) | TC-F11-001 | Integrations Team |
| F12 Roles & permissions | §§2, 3, 6, 7.1 | Identity & Access | GET/POST /api/v1/roles; PUT /api/v1/users/{id}/roles | TC-F12-001 | IAM Team |
