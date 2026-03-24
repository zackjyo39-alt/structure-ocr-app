# MVP Scope and Architecture (Session: 2026-03-23)

## Objective
Ship a production-capable vertical slice that proves end-to-end value with strict scope control and fast iteration.

## MVP Scope Boundaries
### In scope
- Single primary user journey from input to successful outcome.
- Authentication for one actor type only.
- Core data model and CRUD for the primary domain entity.
- One deployable backend service and one frontend client.
- CI gates: lint, unit tests, build, and smoke test.
- Minimal observability: structured logs and health endpoint.

### Out of scope
- Multi-tenant isolation beyond basic ownership checks.
- Role matrix or advanced permissions.
- Billing, invoicing, or enterprise SSO.
- Complex analytics dashboards.
- Background workflow orchestration beyond one synchronous flow.

## Architecture Decisions
1. System shape: modular monolith.
- Reason: reduces coordination overhead while preserving clear module boundaries.
- Constraint: enforce package-level boundaries and avoid cross-module imports.

2. API style: versioned REST (`/api/v1`).
- Reason: simplest surface for MVP clients and testing.
- Constraint: every endpoint must have schema validation and typed responses.

3. Data layer: single relational database.
- Reason: transactional integrity for core workflows.
- Constraint: migrations required for all schema changes.

4. Deployment: single environment first, promote after gates pass.
- Reason: faster cycle time for early learning.
- Constraint: no manual deploys to production target; CI pipeline only.

5. Quality gates: must pass before merge.
- Lint
- Unit tests
- Build
- Smoke test against deployed artifact

## Delivery Constraints
- Keep implementation to one vertical slice only.
- No new infrastructure unless tied to a hard reliability requirement.
- Every PR must include test impact statement.
- Any scope addition requires explicit trade: what gets removed from MVP.

## Execution Plan
1. Freeze acceptance criteria for the vertical slice.
2. Implement backend modules and API contracts.
3. Implement frontend slice against frozen contracts.
4. Add CI gates and deployment automation.
5. Run release readiness check and hand off to `ABC-4` execution.

## Handoff
- Completed in this session: scope boundaries, architecture decisions, and delivery constraints.
- Next highest-value step: execute `ABC-4` using this document as the implementation contract.
