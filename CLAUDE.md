## 1) Purpose and Scope

- This document defines how Claude should work in this repo: planning, execution, verification, and documentation.
- Default objective: deliver correct, maintainable results with minimal disruption.
- If a request is ambiguous, make a best-effort assumption and proceed, but clearly record the assumption in **lessons.md**.

## 2) Operating Principles

- Prefer simple solutions for simple tasks.
- For complex tasks, ask: **Is there a more elegant approach** (fewer moving parts, clearer interfaces, lower risk, better testability)?
- Minimize scope: change only what is necessary to satisfy requirements.
- Preserve invariants and existing architecture unless explicitly asked to refactor.
- Avoid “clever” implementations that reduce readability or increase coupling.
- Always think in terms of failure modes and rollback safety.

## 3) Work Intake and Preconditions

Before coding:

- Restate the goal in 1–3 bullet points.
- List constraints (files allowed to change, time, performance, dependencies).
- Identify “definition of done” checks (tests, lint, build, runtime behavior).
- If the user provided specific file boundaries, follow them strictly.
- If a dependency/tooling choice is unclear, default to existing project conventions.

## 4) Subagents First (Use Them Aggressively)

Use subagents to parallelize and reduce errors. Suggested subagents:

- **Planner**: decomposes work into atomic tasks and acceptance criteria.
- **Repo Scout**: locates relevant files, patterns, and prior art in the codebase.
- **Implementer**: performs focused code edits for a single task ticket.
- **Tester**: adds/updates tests, runs checks, verifies edge cases.
- **Reviewer**: audits diffs for correctness, simplicity, and consistency.
- **Doc Keeper**: updates README/lessons.md and ensures traceability.

Rules:

- Assign one responsibility per subagent.
- Keep subagent prompts narrow, with explicit inputs/outputs.
- Have the Reviewer subagent validate assumptions and failure modes.
- If subagents disagree, prefer the solution with clearer invariants and fewer changes.

## 5) Plan-Then-Execute Workflow

Follow this loop:

1. **Plan**: create a short task list with acceptance criteria per task.
2. **Scout**: locate relevant modules, schemas, tests, conventions.
3. **Implement**: make minimal diffs per task.
4. **Verify**: tests, lint, typecheck, and any runtime validations.
5. **Document**: update **lessons.md** after each fix/update (see Section 9).
6. **Review**: ensure no accidental scope creep; confirm acceptance criteria met.

## 6) Implementation Guidance (Simplicity + Elegance)

- Start with the simplest approach that works.
- If requirements imply complexity (concurrency, idempotency, caching, performance):
  - Prefer explicit interfaces and clear boundaries.
  - Use small, composable functions.
  - Prefer pure logic separated from I/O.
  - Add invariants as assertions or schema validation where appropriate.
  - Avoid hidden coupling (global state, implicit ordering assumptions).
- If the problem is complex, write a brief “Design Snapshot”:
  - Data flow (inputs, transformations, outputs)
  - Trust boundaries (validation points)
  - Failure handling and retries
  - Observability hooks (logs, metrics, traces)

## 7) Testing and Verification Rules

- No change is “done” without a verification step.
- Add tests proportional to risk:
  - Parsing/logic: unit tests with edge cases.
  - API/tooling: contract tests (schemas, status codes, error shapes).
  - UI behavior: component tests or E2E for critical flows.
- Ensure deterministic tests:
  - Stable sorting
  - Fixed fixtures
  - Time and randomness controlled or mocked
- Run the repo’s standard checks (examples):
  - format/lint
  - typecheck
  - unit tests
  - E2E tests (if applicable)

## 8) Code Quality and Change Discipline

- Keep diffs tight. Prefer targeted edits over broad refactors.
- Do not introduce new dependencies unless necessary and justified.
- Maintain consistent naming and project style.
- Avoid breaking API contracts or tool schemas.
- When modifying behavior, update:
  - tests
  - docs
  - any schemas/validators that reflect expectations
- If you change a public interface, document migration notes.

## 9) Documentation: Update lessons.md After Each Fix

After **every** fix/update (even small ones), append an entry to **lessons.md** with:

- **Change summary** (1–3 bullets)
- **Why** (problem/root cause)
- **What worked / what didn’t**
- **Assumptions made**
- **Edge cases considered**
- **Follow-ups** (if any), clearly marked as optional or required
- **Verification performed** (commands run, tests added/updated)

Template:

```md

## YYYY-MM-DD: <short title>

**Summary**
-

**Why**
-

**What worked / what didn’t**
-

**Assumptions**
-

**Edge cases**
-

**Verification**
-

**Follow-ups**
-
