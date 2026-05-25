import os
import psycopg

from flask import Flask, flash, redirect, render_template, request, session, g, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room
from helpers import apology, DECK, build_room_state, get_db
from psycopg import errors as pg_errors
from psycopg.rows import dict_row

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)
socketio = SocketIO(app)

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
                # Create a room for the user
                roomId = db.execute(
                    "INSERT INTO rooms DEFAULT VALUES RETURNING id"
                ).fetchone()[0]

                # Register user for the room
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

@app.route("/room/<uuid:room_id>", methods=["GET"])
def room(room_id):
    """ New Scrum Poker Room """

    # Check if room exists
    db = get_db()
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM rooms WHERE id = %s", (room_id,))
        room = cur.fetchone()

    if not room:
        return apology("room doesn't exist", 404)

    # Check whether participant already has a session value
    participant_id = session.get("participant_id")

    # Check if participant actually exist in database for this room
    if participant_id:
        db = get_db()
        with db.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id
                FROM participants
                WHERE id = %s AND room_id = %s
                """,
                (participant_id, room_id),
            )
            participant = cur.fetchone()

            if participant:
                return render_template("room.html", room_id=room_id, deck=DECK)

    # Redirect when user is no active participant
    return redirect(url_for("lobby", room_id=room_id))

@app.route("/lobby/<uuid:room_id>", methods=["GET", "POST"])
def lobby(room_id):
    """Join new participants to existing Room"""

    # Check if room exist
    db = get_db()
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM rooms WHERE id = %s", (room_id,))
        room = cur.fetchone()

    if not room:
        return apology("room doesn't exist", 404)

    if request.method == "POST":
        # Render an apology if the user’s input is blank
        displayName = request.form.get("displayname").strip()
        if not displayName:
            return apology("must provide display name", 400)

        db = get_db()

        try:
            # Register user for the room
            participantId = db.execute(
                """
                INSERT INTO participants (room_id, display_name)
                VALUES (%s, %s)
                RETURNING id
                """,
                (room_id, displayName),
            ).fetchone()[0]

        except pg_errors.UniqueViolation:
            return apology("display name is already taken", 400)

        session["participant_id"] = participantId
        session["room_id"] = str(room_id)

        # User is redirected to the room
        return redirect(url_for("room", room_id=room_id))

    else:
        return render_template("lobby.html", room_id=room_id)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@socketio.on("join_room")
def handle_join_room(data):
    """Socket IO room handler"""

    room_id = data.get("room_id")
    participant_id = session.get("participant_id")

    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    db = get_db()
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id
            FROM participants
            WHERE id = %s AND room_id = %s
            """,
            (participant_id, room_id),
        )
        participant = cur.fetchone()

    if not participant:
        emit("error", {"message": "Invalid participant"})
        return

    join_room(room_id)
    emit("room_state", build_room_state(room_id), to=room_id)

@socketio.on("vote")
def handle_vote(data):
    """Socket IO vote handler"""

    room_id = data.get("room_id")
    card_value = data.get("vote")
    participant_id = session.get("participant_id")

    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    if card_value not in DECK:
        emit("error", {"message": "Invalid vote"})
        return

    db = get_db()
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id
            FROM participants
            WHERE id = %s AND room_id = %s
            """,
            (participant_id, room_id),
        )
        participant = cur.fetchone()

        if not participant:
            emit("error", {"message": "Invalid participant"})
            return

        cur.execute(
            """
            UPDATE participants
            SET vote = %s
            WHERE id = %s AND room_id = %s
            """,
            (card_value, participant_id, room_id),
        )

    emit("room_state", build_room_state(room_id), to=room_id)

@socketio.on("reveal")
def handle_reveal(data):
    """Socket IO reveal handler"""

    room_id = data.get("room_id")
    participant_id = session.get("participant_id")

    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    db = get_db()
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id
            FROM participants
            WHERE id = %s AND room_id = %s
            """,
            (participant_id, room_id),
        )
        participant = cur.fetchone()

        if not participant:
            emit("error", {"message": "Invalid participant"})
            return

        cur.execute(
            """
            UPDATE rooms
            SET votes_revealed = TRUE
            WHERE id = %s
            """,
            (room_id,),
        )

    emit("room_state", build_room_state(room_id), to=room_id)

@socketio.on("reset")
def handle_reset(data):
    """Socket IO reset handler"""

    room_id = data.get("room_id")
    participant_id = session.get("participant_id")

    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    db = get_db()
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id
            FROM participants
            WHERE id = %s AND room_id = %s
            """,
            (participant_id, room_id),
        )
        participant = cur.fetchone()

        if not participant:
            emit("error", {"message": "Invalid participant"})
            return

        cur.execute(
            """
            UPDATE rooms
            SET votes_revealed = FALSE
            WHERE id = %s
            """,
            (room_id,),
        )
        cur.execute(
            """
            UPDATE participants
            SET vote = NULL
            WHERE room_id = %s
            """,
            (room_id,),
        )

    emit("room_state", build_room_state(room_id), to=room_id)

# Socket IO config
if __name__ == '__main__':
    socketio.run(app)