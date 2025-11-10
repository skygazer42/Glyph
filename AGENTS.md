# Repository Guidelines

## Project Structure & Module Organization
- `app/agents/` hosts AutoGen agents plus the new `AgentService` helpers; add roles under the closest domain module.
- Runtime entry points live in `app/main.py`, `api_server.py`, and the unified `app/agents/service.py` (shared by API/CLI); CLIs stay in `scripts/` (embedding, Milvus maintenance, smart CLI).
- Persist datasets in `data/`, rules/templates in `rules/` + `templates/`, knowledge artifacts in `app/knowledge/` + `knowledge_base/`, and UI code in `web/`.
- Tests live in `tests/` plus root-level `test_*.py`; colocate fixtures beside the feature they validate.

## Build, Test & Development Commands
- `python -m venv .venv && .venv\Scripts\activate; pip install -r requirements.txt` - create and hydrate the backend env.
- `python -m uvicorn api_server:app --reload --env-file .env` - FastAPI service for DSL and knowledge operations.
- `python scripts/unified_cli.py --load-docs data/policies --interactive` - multi-agent CLI session against a local corpus.
- `npm --prefix web install && npm --prefix web run dev` - Vue 3 dashboard pointing at localhost:8000.
- `pytest tests -q && pytest test_api_dsl.py -k regression` - full suite plus a DSL smoke; ensure `PYTHONPATH=.`.

## Coding Style & Naming Conventions
- Use Python 3.9+, 4-space indents, type hints, and `UPPER_SNAKE_CASE` constants; prefer `loguru`/`rich` logging.
- Agent/service classes stay `PascalCase`, methods snake_case unless mirroring JSON fields; keep modules injectable via `config/settings`.
- Vue files follow `PascalCase.vue`, stores in `web/src/stores`, shared styles in `web/src/assets`.

## Testing Guidelines
- Default to `pytest -m "not slow" --maxfail=1`; add async cases under `tests/feature_name/test_*.py`.
- Stub Milvus and LLM clients through dependency overrides; sample payloads belong in `data/` or `tests/fixtures`.
- CLI or notebook demos sit beside their script counterparts (e.g., `test_batch_dsl.py`) and should tag long integrations with `@slow`.

## Commit & Pull Request Guidelines
- Match the concise Chinese imperatives already in history (`增加web服务`, `优化dsl解析`); mention touched modules when scope spans layers.
- Every PR needs a summary, configuration impact, validation evidence (pytest output or CLI transcript), and UI screenshots when relevant.
- Reference issue IDs and detail affected `rule_id`/dataset names when touching `rules/`, `templates/`, or `knowledge_base/`.

## Configuration & Security
- Copy `.env.example` -> `.env`, inject keys locally, and keep shared defaults in `app/config/app_config.py`.
- Keep Milvus/Neo4j endpoints private and scrub uploads before committing anything under `uploads/` or `knowledge_base/`.
- Run `scripts/check_config.py` plus `scripts/check_mineru_config.py` before PRs to ensure environment parity and schema sync.
