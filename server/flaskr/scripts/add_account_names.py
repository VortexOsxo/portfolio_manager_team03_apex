import os
import sys
from pathlib import Path

import mysql.connector

from dotenv import load_dotenv
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _column_exists(cursor, table, column):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s;",
        (os.getenv("DB_NAME"), table, column),
    )
    return cursor.fetchone()[0] > 0


def main():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
    cursor = conn.cursor()

    # no name, it just skips the welcome greeting.
    if not _column_exists(cursor, "accounts", "first_name"):
        cursor.execute("ALTER TABLE accounts ADD COLUMN first_name varchar(50) NULL;")
    if not _column_exists(cursor, "accounts", "last_name"):
        cursor.execute("ALTER TABLE accounts ADD COLUMN last_name varchar(50) NULL;")

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()
