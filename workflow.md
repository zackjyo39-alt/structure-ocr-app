# AI Development Workflow

## Goal

Use an agent harness to convert a product brief into a working system with minimal human intervention.

## Inputs

- `product.md`
- `requirements.md`
- `architecture.md`
- current repository state
- test results

## Workflow

### 1. Read

- Load the three source documents
- Inspect the existing codebase
- Identify the smallest useful implementation slice

### 2. Plan

- Break the work into ordered tasks
- Mark dependencies explicitly
- Identify which tasks can run in parallel
- Define acceptance checks for each task

### 3. Implement

- Make the smallest code change needed for the current task
- Keep file ownership narrow
- Prefer direct implementation over placeholder wrappers

### 4. Verify

- Run syntax checks
- Run unit tests if available
- Run build checks if available
- Run integration checks if the slice touches runtime behavior

### 5. Repair

- If verification fails, inspect the error
- Patch the implementation
- Re-run verification

### 6. Report

- Summarize what changed
- Summarize what passed
- List any remaining gaps

## Agent Rules

- Do not expand scope beyond the current slice
- Do not optimize prematurely
- Do not invent new architecture without a concrete need
- Do not skip verification
- Do not mark work complete before tests pass

