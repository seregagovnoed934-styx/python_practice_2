.PHONY: all lint test coverage run clean

all: lint test coverage

lint:
	python -m flake8 src tests

test:
	python -m pytest tests

coverage:
	python -m coverage run --branch -m pytest tests
	python -m coverage report -m

run:
	python -m src.app

clean:
	python -c "import shutil, os, glob; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', 'htmlcov', '.hypothesis', 'src/__pycache__', 'tests/__pycache__']]; [os.remove(f) for f in glob.glob('*.sqlite3') + glob.glob('*.json') if f not in ['package.json']]; os.remove('.coverage') if os.path.exists('.coverage') else None"
