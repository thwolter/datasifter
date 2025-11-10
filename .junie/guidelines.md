# Project Guidelines for Junie

## Folder Structure

- Source code in `/src`
- Tests in `/tests`

## Architecture Principles

### Async-first

- All I/O (DB, HTTP, LLM) is async
- Use `asyncpg` or `psycopg[pool]` with connection pools
- Do **not** prefix async functions with `a` (e.g. `asave` → `save`)

## Code Style & Tooling

- **Typing:**
  Use `from __future__ import annotations`; strict hints; must be **Pyright-clean**
- **Formatting:**
  Use `ruff`; no unjustified `noqa`
- **Docstrings:**
  Short Google- or NumPy-style docstrings
- **Error handling:**
  Narrow `except`; define custom domain errors
- **Type hints:**
  Use PEP 604 unions (`str | None`, `int | float`)
- **Maintainability:**
  - Group related functionality
  - Keep functions short and focused
  - Use descriptive names; avoid unclear abbreviations
- **No backward compatibility:**
  Refactor all dependent code and tests; delete deprecated code

## Function Parameters & Schemas

- Group parameters by cohesion; use value objects where appropriate
- Use **Pydantic models** at boundaries (API, env, parsing)
- Use **dataclasses** for domain and service layers (`@dataclass(frozen=True)`)
- Always map API DTOs → domain dataclasses explicitly
- Functions should accept cohesive context or command objects (`JobCtx`, `ProcessUploadCommand`)
- Split large schemas into smaller value objects (`UploadHints`, `StorageLocation`, `IngestionPolicy`)
- Version commands explicitly when flows change (`CommandV2`)

## Logging

- Prefer structured JSON with `correlation_id`
- Mask sensitive data; never log raw content

## Commit Message Standard

Follow [Conventional Commits](https://www.conventionalcommits.org/) format using clear, professional language.
Avoid formatting symbols such as asterisks (`*`) or bold markers (`**`).

**Example:**

```
feat(api): add async support for document ingestion
fix(tests): correct mock for extraction pipeline
refactor(core): simplify vectorstore initialisation
```
