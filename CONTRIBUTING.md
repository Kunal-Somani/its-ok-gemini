# Contributing Guide

## Local Development
1. Use Python 3.11+. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
2. Run tests: `make test`

## Code Style
- We strictly enforce **Ruff** for linting and formatting.
- Check style: `make lint`
- Auto-format: `make format`

## Branch Naming
- `feat/something` for features.
- `fix/something` for bugfixes.
- `chore/something` for internal config changes.

## Adding an LLM Backend
To add a new LLM provider, create a new class implementing the `generate_code` signature in `app/services/llm_service.py`. Update `app/core/config.py` to add any requisite API keys.
