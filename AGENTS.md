# Repository Guidelines

## Project Structure & Module Organization
- Core runtime lives in `src/datasifter/`, with orchestration helpers under `graph/`, adapter contracts in `interfaces.py`, registries in `registry/`, and execution glue in `runner.py`.
- Shared schemas, prompts, and thresholds live alongside the runner to keep attribute metadata versioned with code.
- MkDocs content sits in `docs/` and is wired by `mkdocs.yml`; favor this area for longer-form explanations and examples.
- Packaging metadata (`pyproject.toml`, `uv.lock`) controls dependencies and build settings—update both when adding libraries.

## Build, Test, and Development Commands
- `uv pip sync` — install the locked toolchain locally; run after modifying dependencies.
- `uv run pytest` — execute the full test suite; add `-k name` for focused runs.
- `uv run ruff check src tests` and `uv run ruff format src tests` — enforce linting and formatting.
- `uv run mkdocs serve` — preview documentation at `http://127.0.0.1:8000`.
- `uv build` — produce a distribution if you need to validate publishing.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents and explicit type hints; all public APIs should be typed.
- Prefer dataclass-like Pydantic models for data contracts and keep adapters protocol-oriented (see `interfaces.py`).
- Name orchestration components with their role (`*_runner`, `*_adapter`, `*_registry`); tests should mirror module names (e.g., `test_runner.py`).
- Run `ruff format` before committing; avoid manual import ordering—`isort`/`ssort` rules are already embedded in Ruff.

## Testing Guidelines
- Use `pytest` fixtures for runner and registry scenarios; seed fake adapters inside `tests/fixtures/` (create if missing).
- Add unit tests beside their target module in `tests/` using `test_<module>.py` and descriptive test names (`test_handles_missing_threshold`).
- Maintain coverage for new branches and serialization paths; add regression tests whenever you touch schemas or prompts.

## Commit & Pull Request Guidelines
- Write Conventional Commit messages via `cz commit` (e.g., `feat(registry): add pdf registry hook`) so release notes stay automated.
- Keep PRs atomic: describe the change, link related issues, mention new commands/tests, and attach screenshots for doc or UX updates.
- Ensure CI commands (`uv run pytest`, `uv run ruff check`) pass locally before requesting review.

## Security & Configuration Tips
- Never commit secrets; load API keys via environment variables consumed by your adapters.
- Keep optional IO adapters isolated behind interfaces so sensitive dependencies remain out of the core package.
