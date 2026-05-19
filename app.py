import os
import psycopg

from flask import Flask, flash, redirect, render_template, request, session, g, url_for
from flask_session import Session
from helpers import apology, DECK
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

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
    # Future Feature

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
            db = get_db()

            try:
                # A room is created for the user
                roomId = db.execute(
                    "INSERT INTO rooms DEFAULT VALUES RETURNING id"
                ).fetchone()[0]

                # The user is registered for the room
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

            # User is redirected to the room
            return redirect(url_for("room", room_id=session["room_id"]))

    # When GET render the Create Room template
    else:
        return render_template("create.html")

@app.route("/room/<uuid:room_id>", methods=["GET", "POST"])
def room(room_id):
    """ New Scrum Poker Room """
    if request.method == "POST":

        # Card vote isn't empty
        if not request.form.get("vote"):
            return apology("Card vote invalid", 400)

        else:
            # Get symbol from form request
            cardValue = request.form.get("vote")
            # Update participants database with chosen vote / card vote
            db = get_db()
            with db.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "UPDATE participants SET vote = %s WHERE id = %s AND room_id = %s", 
                    (cardValue, session["participant_id"], room_id)
                )
                # Retrieve values from participants database after update
                cur.execute(
                "SELECT id, display_name, vote FROM participants WHERE room_id = %s ORDER BY joined_at",
                (room_id,),
                )
                participants = cur.fetchall()
                print("successful POST!")
            return render_template("room.html", room_id=room_id, participants=participants, deck=DECK)
        

    else:
        # GET request
        db = get_db()
        with db.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, display_name, vote FROM participants WHERE room_id = %s ORDER BY joined_at",
                (room_id,),
            )
            participants = cur.fetchall()
        return render_template("room.html", room_id=room_id, participants=participants, deck=DECK)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")