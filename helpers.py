import os
import psycopg

from flask import render_template, g
from psycopg.rows import dict_row

# Possible card values for voting
DECK = ("1", "2", "3", "5", "8", "13", "20", "40", "100", "?", "coffee")

def apology(message, code=400):
    """Render message as an apology to user."""

    # Escape special characters
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code

def build_room_state(room_id):
    """Build room_state payload for Socket IO"""

    db = get_db()
    # Get the room's votes_revealed and the participants' IDs, display names, and votes
    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT votes_revealed
            FROM rooms
            WHERE id = %s
            """,
            (room_id,),
        )
        room = cur.fetchone()

        # Get the participants' IDs, display names, and votes
        cur.execute(
            """
            SELECT id, display_name, vote
            FROM participants
            WHERE room_id = %s
            ORDER BY joined_at
            """,
            (room_id,),
        )
        participants = cur.fetchall()

    # Get the room's votes_revealed and the current participant's vote
    votes_revealed = room["votes_revealed"]

    # Return the room state
    return {
        "room_id": str(room_id),
        "votes_revealed": votes_revealed,
        "participants": [
            {
                "id": participant["id"],
                "display_name": participant["display_name"],
                "has_voted": participant["vote"] is not None,
                "vote": participant["vote"] if votes_revealed else None,
            }
            for participant in participants
        ],
    }


def build_participant_state(room_id, participant_id):
    """Build participant-specific Socket IO payload."""

    current_vote = None
    db = get_db()

    with db.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT vote
            FROM participants
            WHERE id = %s AND room_id = %s
            """,
            (participant_id, room_id),
        )
        participant = cur.fetchone()

    if participant:
        current_vote = participant["vote"]

    return {
        "room_id": str(room_id),
        "current_vote": current_vote,
    }


def get_db():
    """Get a database connection"""

    # If the database connection is not in the global context, create it
    if "db" not in g:
        g.db = psycopg.connect(os.environ["DATABASE_URL"])
    return g.db
