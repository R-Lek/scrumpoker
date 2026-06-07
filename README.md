# Scrum Poker web app
### Video Demo: https://www.youtube.com/watch?v=ykbmq5ncoPY
### Description:

Scrum Poker is a small real-time planning poker web app for estimating work with a team.
One person creates a room, shares the room link, and everyone joins with a display name.
Participants pick estimate cards while votes stay hidden, then the room reveals all submitted votes at the same time.

The app is built with Flask, Jinja templates, Flask-SocketIO, and PostgreSQL.

### Current features

- Create a new Scrum Poker room
- Join an existing room by opening its room link
- Choose a display name; no user accounts are required
- Vote with the deck: `1`, `2`, `3`, `5`, `8`, `13`, `20`, `40`, `100`, `?`, coffee
- Keep votes hidden until they are revealed
- Reset the room for a new voting round
- Store rooms, participants, and votes in PostgreSQL

### How the app works

The browser loads normal Flask pages and then connects to the server through Socket.IO for real-time room updates.
The server is the source of truth: it stores the room state in PostgreSQL and sends each client the latest room state after joins, votes, reveals, and resets.

For local development, the database is not inside this project folder.
Each person running the app needs their own PostgreSQL database and must load `schema.sql`.

### Project files

- `app.py`: Flask routes and Socket.IO event handlers
- `helpers.py`: shared helper functions and database connection logic
- `schema.sql`: PostgreSQL schema needed by the app
- `templates/`: Jinja HTML templates
- `static/`: CSS and image assets
- `requirements.txt`: Python dependencies
- `Makefile`: convenience commands for local development

### Prerequisites

- Python 3.12+
- PostgreSQL 13+; PostgreSQL 16 is used locally
- A browser with access to the Bootstrap and Socket.IO CDN files used in `templates/layout.html`

### Local setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create a local database and load the schema:

```bash
createdb scrumpoker
psql -d scrumpoker -f schema.sql
```

Run the app with a database URL that matches your local PostgreSQL user:

```bash
DATABASE_URL="postgresql://YOUR_USER@localhost:5432/scrumpoker" ./.venv/bin/python -m flask --app app run --debug
```

If your PostgreSQL user requires a password, use:

```bash
DATABASE_URL="postgresql://YOUR_USER:YOUR_PASSWORD@localhost:5432/scrumpoker" ./.venv/bin/python -m flask --app app run --debug
```

You can also run through the Makefile:

```bash
make init-db
make run
```

Or pass a custom database URL:

```bash
make DATABASE_URL="postgresql://YOUR_USER@localhost:5432/scrumpoker" init-db
make DATABASE_URL="postgresql://YOUR_USER@localhost:5432/scrumpoker" run
```

Open the app at:

```text
http://127.0.0.1:5000
```

### First-time usage

1. Open `http://127.0.0.1:5000`.
2. Click `New Room`.
3. Enter your display name and create the room.
4. Copy the room link and share it with another local browser or another user who can reach the running server.
5. Each participant picks a card.
6. Click `Reveal cards` to show votes.
7. Click `Start new voting` to clear votes and start another round.

### Database configuration

The app reads its database connection from the `DATABASE_URL` environment variable in `helpers.py`.

Example:

```text
postgresql://localhost:5432/scrumpoker
```

The local database files are managed by PostgreSQL and should not be copied into this repo.
To share the app with another developer, share the project folder or Git repository and have them create their own database from `schema.sql`.

Do not share:

- Your local PostgreSQL data directory
- Your `.venv` folder
- Database passwords
- Production `DATABASE_URL` values

### Current limitations

- There are no user accounts or passwords.
- There is no room expiration or automatic cleanup yet.
- Votes are stored directly on `participants`; there is no separate voting-round history table yet.
- The `Copy Room` button currently builds a local `http://127.0.0.1:5000/room/...` URL in `templates/room.html`.
  Update that before deploying publicly, or generate the room URL from the current request host.

### Deployment notes

For sharing with real users, run the Flask app on a server that supports WebSockets.
Traditional shared hosting often does not support this well.

A typical deployment needs:

- The app code
- A PostgreSQL database
- A production `DATABASE_URL` environment variable
- A non-default `SECRET_KEY` environment variable
- A process manager such as systemd
- A reverse proxy such as Nginx with WebSocket proxying enabled
- HTTPS
- Database backups

Keep PostgreSQL private where possible.
Users should access the web app, not the database directly.

### Troubleshooting

If the app cannot start, check that `DATABASE_URL` is set and that PostgreSQL is running.
If rooms fail to create, confirm that `schema.sql` has been loaded into the database.
If real-time updates do not work, confirm the browser can load the Socket.IO client script from the CDN and that the server/proxy allows WebSocket connections.
