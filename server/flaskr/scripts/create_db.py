import os
import sys
from pathlib import Path

import mysql.connector

from dotenv import load_dotenv
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



def main():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    cursor = conn.cursor()

    schema_path = os.path.join(os.path.dirname(__file__), "schemas.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    statements = [stmt.strip() for stmt in sql_script.split(";") if stmt.strip()]
    for statement in statements:
        cursor.execute(statement)

    conn.commit()
    
    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()