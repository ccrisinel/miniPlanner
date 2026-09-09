"""miniPlanner : qui bosse sur quoi, en un coup d'oeil."""

import os

from .app import create_app

__all__ = ["create_app", "main"]


def main() -> None:
    app = create_app()
    app.run(
        host=os.environ.get("MINIPLANNER_HOST", "0.0.0.0"),
        port=int(os.environ.get("MINIPLANNER_PORT", "5000")),
        debug=os.environ.get("MINIPLANNER_DEBUG") == "1",
    )
