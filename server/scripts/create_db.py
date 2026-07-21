import os
import mysql.connector


def main():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="password"
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