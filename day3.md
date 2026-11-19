load the tickets into a database, safely

1. SQLite: a database live in one file, using it by import sqlite3

2. MODIFY DATABASE:
    . conn = sqlite3.connect(path): this opens a pipeline between your Python script and the `tickets.db` file on disk. If `tickets.db` does not exist yet, SQLite automatically creates an empty file for you. `conn` (the connection) holds the overall session open
    . cursor = conn.cursor(): The connection (`conn`) manages the file, but it cannot run SQL commands by itself. A **cursor** is an active worker object that moves through the database to execute queries, hold query results in RAM, and fetch rows.
    ___________________________________________________________
    . cursor.execute():execute query and modify databse 
    . INSERT OR REPLACE: add this row, or if a row with the same primary key exists, replace it instead of adding a second one.
    . con.commit(): like pressing "SAVE" buttin, SQLite keeps the changes in a temoprary safety buffer -> .commit() save permanently in disk.
    . .fetchall()/ fetchone(): to display whatever the cursor holding in RAM
3. Idempotent: safe to run again. Twice gives the same result as once. That’s the point of today.