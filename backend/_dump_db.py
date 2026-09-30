import os

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()
host = os.environ["DB_HOST"]
port = os.environ["DB_PORT"]
user = os.environ["DB_USER"]
password = os.environ["DB_PASSWORD"]
name = os.environ["DB_NAME"]
ssl = os.environ.get("DB_SSLMODE", "disable")
if ssl.lower() in ("off", "false", "0", "none"):
    ssl = "disable"

conninfo = (
    f"host={host} port={port} dbname={name} user={user} "
    f"password={password} sslmode={ssl} connect_timeout=10"
)
print("connecting", host, port, name, "sslmode=" + ssl)
try:
    conn = psycopg.connect(conninfo)
except Exception as exc:
    print("CONNECT_FAIL", type(exc).__name__, exc)
    raise SystemExit(1)

print("connected")
with conn.cursor(row_factory=dict_row) as cur:
    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
        """
    )
    tables = cur.fetchall()
    print("TABLE_COUNT", len(tables))
    for table in tables:
        schema = table["table_schema"]
        name_ = table["table_name"]
        ident = f'"{schema}"."{name_}"'
        cur.execute(f"SELECT COUNT(*) AS n FROM {ident}")
        count = cur.fetchone()["n"]
        print(f"--- {schema}.{name_} rows={count}")
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, name_),
        )
        cols = cur.fetchall()
        print(
            "COLS",
            ", ".join(f"{c['column_name']}:{c['data_type']}" for c in cols),
        )
        binary = {c["column_name"] for c in cols if c["data_type"] == "bytea"}
        select_cols = []
        for col in cols:
            cn = col["column_name"]
            if cn in binary:
                select_cols.append(f'octet_length("{cn}") AS "{cn}_bytes"')
            else:
                select_cols.append(f'"{cn}"')
        cur.execute(
            f"SELECT {', '.join(select_cols)} FROM {ident} LIMIT 200"
        )
        rows = cur.fetchall()
        for index, row in enumerate(rows, 1):
            safe = {}
            for key, value in row.items():
                text = str(value)
                if len(text) > 300:
                    text = text[:300] + f"...<{len(str(value))} chars>"
                safe[key] = text
            print(f"ROW {index}", safe)
        if count > 200:
            print(f"... truncated, showing 200 of {count}")
conn.close()
