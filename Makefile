dev:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	python -m pytest -q


