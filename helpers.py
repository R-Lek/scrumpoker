import os
import psycopg
import requests

from flask import redirect, render_template, session, g
from functools import wraps
from psycopg.rows import dict_row

DECK = ("1", "2", "3", "5", "8", "13", "20", "40", "100", "?", "coffee")

def apology(message, code=400):
    """Render message as an apology to user."""

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

    votes_revealed = room["votes_revealed"]

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


def get_db():
    if "db" not in g:
        g.db = psycopg.connect(os.environ["DATABASE_URL"])
    return g.db
