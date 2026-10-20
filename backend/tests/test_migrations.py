import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND = Path(__file__).resolve().parents[1]
EXPECTED = {
    "drivers", "riders", "rides", "ride_assignments", "trip_events",
    "fare_transactions", "surge_history", "driver_location_history",
}


def test_migrations_create_every_table(tmp_path):
    db_file = tmp_path / "migrated.db"
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    command.upgrade(cfg, "head")
    connection = sqlite3.connect(db_file)
    tables = {row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
    connection.close()
    assert EXPECTED <= tables
    