"""SQLite storage for the board: people -> cards -> lines."""

import os
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
    id       INTEGER PRIMARY KEY,
    name     TEXT    NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS card (
    id        INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES person(id) ON DELETE CASCADE,
    title     TEXT    NOT NULL,
    position  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS item (
    id       INTEGER PRIMARY KEY,
    card_id  INTEGER NOT NULL REFERENCES card(id) ON DELETE CASCADE,
    text     TEXT    NOT NULL,
    position INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS card_by_person ON card(person_id, position);
CREATE INDEX IF NOT EXISTS item_by_card   ON item(card_id, position);
"""


def db_path(app):
    env = os.environ.get("MINIPLANNER_DB")
    if env:
        return Path(env)
    return Path(app.instance_path) / "planner.db"


def get_db():
    if "db" not in g:
        path = db_path(current_app)
        path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path, timeout=15)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        # Several gunicorn workers write to the same file: wait for the lock
        # instead of failing straight away.
        g.db.execute("PRAGMA busy_timeout = 5000")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        # WAL lets reads and writes run concurrently. The setting is stored in
        # the file itself, so it only needs to be set once.
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(SCHEMA)
        db.commit()


def next_position(db, table, column, parent_id):
    """Next position within a parent (table/column are internal constants)."""
    row = db.execute(
        f"SELECT COALESCE(MAX(position), -1) + 1 AS p FROM {table} WHERE {column} = ?",
        (parent_id,),
    ).fetchone()
    return row["p"]


def next_person_position(db):
    row = db.execute("SELECT COALESCE(MAX(position), -1) + 1 AS p FROM person").fetchone()
    return row["p"]
