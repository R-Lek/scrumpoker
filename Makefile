run:
	DATABASE_URL="postgresql://randy@localhost:5432/scrumpoker" ./.venv/bin/python -m flask --app app run --debug

database:
	psql -U randy -d scrumpoker

postgres:
	# DATABASE_URL="postgresql://USER:PASSWORD@localhost:5432/scrumpoker" python -m flask --app app run --debug
