"""Entry point. Run with: python app.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.config.settings import get_settings
from src.db.database import get_engine

if __name__ == "__main__":
    settings = get_settings()

    # Pre-load the database
    print("Initialising Chinook database…")
    get_engine()
    print("Database ready.")

    import subprocess

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/ui/streamlit_app.py",
            "--server.port",
            str(settings.port),
        ],
        check=True,
    )
