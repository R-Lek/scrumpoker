import os

from flask import Flask, redirect, render_template, request, session, g, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room
from helpers import apology, DECK, build_participant_state, build_room_state, get_db
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
    """Close request DB connection"""
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

            # If the display name is already taken, render an apology
            except pg_errors.UniqueViolation:
                return apology("display name is already taken", 400)

            # Remember which room and participant belong to this browser session
            session["room_id"] = str(roomId)
            session["participant_id"] = participantId

            # User is redirected to the room
            return redirect(url_for("room", room_id=session["room_id"]))

    else:
        # Render the Create Room template
        return render_template("create.html")

@app.route("/room/<uuid:room_id>", methods=["GET"])
def room(room_id):
    """ New Scrum Poker Room """

    # Check if room exists in database
    db = get_db()
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM rooms WHERE id = %s", (room_id,))
        room = cur.fetchone()

    if not room:
        return apology("room doesn't exist", 404)

    participant_id = session.get("participant_id")

    # Check if the user is already a participant in this room
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

    # Redirect to lobby if user is not a participant
    return redirect(url_for("lobby", room_id=room_id))

@app.route("/lobby/<uuid:room_id>", methods=["GET", "POST"])
def lobby(room_id):
    """Join new participants to existing Room"""

    # Check if room exists in database
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

        # Remember which participant belongs to this browser session
        session["participant_id"] = participantId
        session["room_id"] = str(room_id)

        # User is redirected to the room
        return redirect(url_for("room", room_id=room_id))

    else:
        # Render the Lobby template
        return render_template("lobby.html", room_id=room_id)


@app.route("/logout")
def logout():
    """Log participant out of the current room"""

    # Get the room and participant IDs from the session
    room_id = session.get("room_id")
    participant_id = session.get("participant_id")

    # If the room and participant IDs are in the session, delete the participant from the database and emit the room state
    if room_id and participant_id:
        db = get_db()
        db.execute(
            """
            DELETE FROM participants
            WHERE id = %s AND room_id = %s
            """,
            (participant_id, room_id),
        )

        socketio.emit("room_state", build_room_state(room_id), to=room_id)

    session.clear()

    # Redirect the user to the home page
    return redirect("/")

# The participant actions was amplified by using Codex to introduce Socket IO
@socketio.on("join_room")
def handle_join_room(data):
    """Socket IO room handler"""

     # Get the room ID from the data sent by the client and the participant ID from the session
    room_id = data.get("room_id")
    participant_id = session.get("participant_id")

    # If the user is not a participant, emit an error
    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    # Check if the participant exists in the database
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

    # If the participant does not exist, emit an error
    if not participant:
        emit("error", {"message": "Invalid participant"})
        return

    # Join the room and emit the room state
    join_room(room_id)
    emit("room_state", build_room_state(room_id), to=room_id)
    emit("participant_state", build_participant_state(room_id, participant_id))

@socketio.on("vote")
def handle_vote(data):
    """Socket IO vote handler"""

    # Get the room ID and the card value from the data sent by the client and the participant ID from the session
    room_id = data.get("room_id")
    card_value = data.get("vote")
    participant_id = session.get("participant_id")

    # If the user is not a participant, emit an error
    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    # If the vote is not in the deck, emit an error
    if card_value not in DECK:
        emit("error", {"message": "Invalid vote"})
        return

    # Update the participant's vote in the database
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

        # If the participant does not exist, emit an error
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

    # Emit the room state to the client
    emit("room_state", build_room_state(room_id), to=room_id)
    # Emit the participant state to the client
    emit("participant_state", build_participant_state(room_id, participant_id))

@socketio.on("reveal")
def handle_reveal(data):
    """Socket IO reveal handler"""

    # Get the room ID from the data sent by the client and the participant ID from the session
    room_id = data.get("room_id")
    participant_id = session.get("participant_id")

    # If the user is not a participant, emit an error
    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    # Check if the participant exists in the database
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

        # If the participant does not exist, emit an error
        if not participant:
            emit("error", {"message": "Invalid participant"})
            return

        # Update the room's votes_revealed to true
        cur.execute(
            """
            UPDATE rooms
            SET votes_revealed = TRUE
            WHERE id = %s
            """,
            (room_id,),
        )

    # Emit the room state to the client
    emit("room_state", build_room_state(room_id), to=room_id)

@socketio.on("reset")
def handle_reset(data):
    """Socket IO reset handler"""

    # Get the room ID from the data sent by the client and the participant ID from the session
    room_id = data.get("room_id")
    participant_id = session.get("participant_id")

    # If the user is not a participant, emit an error
    if not participant_id:
        emit("error", {"message": "Not joined"})
        return

    # Check if the participant exists in the database
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

        # If the participant does not exist, emit an error
        if not participant:
            emit("error", {"message": "Invalid participant"})
            return

        # Update the room's votes_revealed to false
        cur.execute(
            """
            UPDATE rooms
            SET votes_revealed = FALSE
            WHERE id = %s
            """,
            (room_id,),
        )

        # Update the participants' votes to null
        cur.execute(
            """
            UPDATE participants
            SET vote = NULL
            WHERE room_id = %s
            """,
            (room_id,),
        )

    # Emit the room state to the client
    emit("room_state", build_room_state(room_id), to=room_id)

# Socket IO config
if __name__ == '__main__':
    socketio.run(app)
