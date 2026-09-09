"""miniPlanner - a minimal board: one column per person, cards you can drag around."""

from flask import Flask, render_template, request

from .db import close_db, get_db, init_db, next_person_position, next_position


def create_app(**config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(config)
    app.teardown_appcontext(close_db)
    init_db(app)
    register_routes(app)
    return app


# --- reading -----------------------------------------------------------------


def load_columns():
    """The whole board: people -> cards -> lines, already ordered."""
    db = get_db()
    people = db.execute("SELECT * FROM person ORDER BY position, id").fetchall()
    cards = db.execute("SELECT * FROM card ORDER BY position, id").fetchall()
    items = db.execute("SELECT * FROM item ORDER BY position, id").fetchall()

    lines_by_card = {}
    for item in items:
        lines_by_card.setdefault(item["card_id"], []).append(item)

    cards_by_person = {}
    for card in cards:
        cards_by_person.setdefault(card["person_id"], []).append(
            {"row": card, "lines": lines_by_card.get(card["id"], [])}
        )

    return [
        {"row": person, "cards": cards_by_person.get(person["id"], [])}
        for person in people
    ]


def load_column(person_id):
    for column in load_columns():
        if column["row"]["id"] == person_id:
            return column
    return None


def load_card(card_id):
    db = get_db()
    card = db.execute("SELECT * FROM card WHERE id = ?", (card_id,)).fetchone()
    if card is None:
        return None
    lines = db.execute(
        "SELECT * FROM item WHERE card_id = ? ORDER BY position, id", (card_id,)
    ).fetchall()
    return {"row": card, "lines": lines}


# --- rendering ---------------------------------------------------------------


def board_html(edit=None):
    return render_template("partials/board.html", columns=load_columns(), edit=edit)


def column_html(person_id, edit=None):
    column = load_column(person_id)
    if column is None:
        return ""
    return render_template("partials/column.html", column=column, edit=edit)


def stale():
    """The resource is gone: the client view is stale, so resynchronise it."""
    return "", 404, {"HX-Refresh": "true"}


def card_html(card_id, edit=None):
    card = load_card(card_id)
    if card is None:
        return ""
    return render_template("partials/card.html", card=card, edit=edit)


# --- routes ------------------------------------------------------------------


def register_routes(app):
    @app.get("/")
    def board():
        return render_template("board.html", columns=load_columns(), edit=None)

    @app.get("/board")
    def board_fragment():
        return board_html()

    # people / columns

    @app.get("/people/new")
    def new_person():
        return board_html(edit=("new-person", 0))

    @app.post("/people")
    def create_person():
        name = request.form.get("name", "").strip()
        if name:
            db = get_db()
            db.execute(
                "INSERT INTO person (name, position) VALUES (?, ?)",
                (name, next_person_position(db)),
            )
            db.commit()
        return board_html()

    @app.get("/people/<int:person_id>/edit")
    def edit_person(person_id):
        return board_html(edit=("person", person_id))

    @app.put("/people/<int:person_id>")
    def rename_person(person_id):
        name = request.form.get("name", "").strip()
        if name:
            db = get_db()
            db.execute("UPDATE person SET name = ? WHERE id = ?", (name, person_id))
            db.commit()
        return board_html()

    @app.delete("/people/<int:person_id>")
    def delete_person(person_id):
        db = get_db()
        db.execute("DELETE FROM person WHERE id = ?", (person_id,))
        db.commit()
        return board_html()

    @app.get("/columns/<int:person_id>")
    def show_column(person_id):
        return column_html(person_id) or stale()

    # cards

    @app.get("/people/<int:person_id>/cards/new")
    def new_card(person_id):
        return column_html(person_id, edit=("new-card", person_id))

    @app.post("/people/<int:person_id>/cards")
    def create_card(person_id):
        title = request.form.get("title", "").strip()
        if title:
            db = get_db()
            db.execute(
                "INSERT INTO card (person_id, title, position) VALUES (?, ?, ?)",
                (person_id, title, next_position(db, "card", "person_id", person_id)),
            )
            db.commit()
        return column_html(person_id) or stale()

    @app.get("/cards/<int:card_id>")
    def show_card(card_id):
        return card_html(card_id) or stale()

    @app.get("/cards/<int:card_id>/edit")
    def edit_card(card_id):
        return card_html(card_id, edit=("card", card_id)) or stale()

    @app.put("/cards/<int:card_id>")
    def rename_card(card_id):
        title = request.form.get("title", "").strip()
        if title:
            db = get_db()
            db.execute("UPDATE card SET title = ? WHERE id = ?", (title, card_id))
            db.commit()
        return card_html(card_id) or stale()

    @app.delete("/cards/<int:card_id>")
    def delete_card(card_id):
        db = get_db()
        card = db.execute("SELECT person_id FROM card WHERE id = ?", (card_id,)).fetchone()
        if card is None:
            return stale()
        db.execute("DELETE FROM card WHERE id = ?", (card_id,))
        db.commit()
        return column_html(card["person_id"])

    # lines

    @app.post("/cards/<int:card_id>/items")
    def create_item(card_id):
        text = request.form.get("text", "").strip()
        if text:
            db = get_db()
            db.execute(
                "INSERT INTO item (card_id, text, position) VALUES (?, ?, ?)",
                (card_id, text, next_position(db, "item", "card_id", card_id)),
            )
            db.commit()
        # hand focus back to the input so lines can be typed one after another
        return card_html(card_id, edit=("add-item", card_id)) or stale()

    @app.get("/items/<int:item_id>/edit")
    def edit_item(item_id):
        db = get_db()
        item = db.execute("SELECT card_id FROM item WHERE id = ?", (item_id,)).fetchone()
        if item is None:
            return stale()
        return card_html(item["card_id"], edit=("item", item_id))

    @app.put("/items/<int:item_id>")
    def update_item(item_id):
        db = get_db()
        item = db.execute("SELECT card_id FROM item WHERE id = ?", (item_id,)).fetchone()
        if item is None:
            return stale()
        text = request.form.get("text", "").strip()
        if text:
            db.execute("UPDATE item SET text = ? WHERE id = ?", (text, item_id))
        else:
            # clearing a line deletes it
            db.execute("DELETE FROM item WHERE id = ?", (item_id,))
        db.commit()
        return card_html(item["card_id"])

    @app.delete("/items/<int:item_id>")
    def delete_item(item_id):
        db = get_db()
        item = db.execute("SELECT card_id FROM item WHERE id = ?", (item_id,)).fetchone()
        if item is None:
            return stale()
        db.execute("DELETE FROM item WHERE id = ?", (item_id,))
        db.commit()
        return card_html(item["card_id"])

    # moving cards

    @app.post("/reorder")
    def reorder():
        """Receives the whole board state: "personId:cardId,cardId;personId:..."."""
        db = get_db()
        for chunk in request.form.get("state", "").split(";"):
            if ":" not in chunk:
                continue
            person_id, _, card_ids = chunk.partition(":")
            if not person_id.isdigit():
                continue
            for position, card_id in enumerate(filter(None, card_ids.split(","))):
                if card_id.isdigit():
                    db.execute(
                        "UPDATE card SET person_id = ?, position = ? WHERE id = ?",
                        (int(person_id), position, int(card_id)),
                    )
        db.commit()
        return "", 204
