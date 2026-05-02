.PHONY: test test-unit test-integration lint format install-hooks pre-push check

install-hooks:
	git config core.hooksPath .githooks
	chmod +x .githooks/pre-push

pre-push:
	bash .githooks/pre-push

check:
	ruff check app/ tests/
	ruff format app/ tests/ --check
	cd frontend && npx tsc --noEmit

test:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check app/ tests/

format:
	ruff format app/ tests/
