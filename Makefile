UV ?= uv
NPM ?= npm

install:
	$(UV) sync --extra dev
	cd frontend && $(NPM) install

run-api:
	$(UV) run api

run-ui:
	cd frontend && $(NPM) run dev

ingest:
	$(UV) run python scripts/ingest_documents.py --input "data/uploads/Nội Quy và Văn Hóa của Việt Thái Dương.docx" --input "data/uploads/Quy Định và Kiến Thức Cơ bản.docx"

add-document:
	$(UV) run python scripts/add_document.py --input "$(INPUT)"

inspect:
	$(UV) run python scripts/inspect_chunks.py

evaluate:
	$(UV) run python scripts/evaluate_retrieval.py

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check . --no-cache

harness-check:
	$(UV) run python scripts/check_harness.py

check: lint test harness-check

ui-build:
	cd frontend && $(NPM) run build

format:
	$(UV) run ruff format .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f
