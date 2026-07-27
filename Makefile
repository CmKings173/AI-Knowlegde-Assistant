UV ?= uv

install:
	$(UV) sync --extra dev

run-api:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	$(UV) run streamlit run ui/streamlit_app.py

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
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f
