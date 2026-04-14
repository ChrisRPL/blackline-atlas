install:
	python3 -m pip install -e ".[dev]"

dev:
	python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check . --fix

train-local:
	python3 training/scripts/train_adapter.py

eval-local:
	python3 training/scripts/eval_structured_outputs.py

