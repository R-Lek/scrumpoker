import os
import psycopg

from flask import Flask, flash, redirect, render_template, request, session, g
from flask_session import Session
from helpers import apology
from psycopg import errors as pg_errors

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def get_db():
    if "db" not in g:
        g.db = psycopg.connect(os.environ["DATABASE_URL"])
    return g.db

@app.teardown_request
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        if exc is None:
            db.commit()
        else:
            db.rollback()
        db.close()

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    """Show Scrum Poker rooms"""

    # Use %s placeholders with psycopg (not ? like SQLite).
    # Always pass parameters as a tuple/list (prevents SQL injection).

    # db = get_db()
    # with db.cursor() as cur:
    #     cur.execute("SELECT id FROM rooms WHERE id = %s", (room_id,))
    #     row = cur.fetchone()

    return render_template("index.html")

@app.route("/create", methods=["GET", "POST"])
def create():
    """Create room"""

    if request.method == "POST":
        displayName = request.form.get("displayname")

        # Render an apology if the user’s input is blank
        if not displayName:
            return apology("must provide display name", 400)

        else:
            print("we're in")
            db = get_db()

            try:
                roomId = db.execute(
                    "INSERT INTO rooms DEFAULT VALUES RETURNING id"
                ).fetchone()[0]

                participantId = db.execute(
                    """
                    INSERT INTO participants (room_id, display_name)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (roomId, displayName),
                ).fetchone()[0]

            except pg_errors.UniqueViolation:
                return apology("display name is already taken", 400)

            session["room_id"] = str(roomId)
            session["participant_id"] = participantId

            return redirect(f"/room/{roomId}")

    # When it's a GET, go to the register.html page to register a user account
    else:
        return render_template("create.html")


# @app.route("/room/<uuid:room_id>")
# def room(room_id):
#     db = get_db()
#     row = db.execute(
#         "SELECT id, display_name, vote FROM participants WHERE room_id = %s ORDER BY joined_at",
#         (room_id,),
#     ).fetchall()
#     participants = row  # list of tuples; or use row_factory for dicts
#     return render_template("room.html", room_id=room_id, participants=participants)

