DATABASE_URL ?= postgresql://localhost:5432/scrumpoker
PYTHON ?= ./.venv/bin/python

run:
	DATABASE_URL="$(DATABASE_URL)" $(PYTHON) -m flask --app app run --debug

database:
	psql "$(DATABASE_URL)"

init-db:
	psql "$(DATABASE_URL)" -f schema.sql

postgres:
	# DATABASE_URL="postgresql://USER:PASSWORD@localhost:5432/scrumpoker" python -m flask --app app run --debug

dependencies:
	.venv/bin/pip install -r requirements.txt
