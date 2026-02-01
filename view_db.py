import sqlite3

conn = sqlite3.connect("furnishfusion.db")

# show tables
print("Tables:", conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())

print("\n--- USERS ---")
for row in conn.execute("SELECT * FROM users").fetchall():
    print(row)

print("\n--- PRODUCTS ---")
for row in conn.execute("SELECT * FROM products").fetchall():
    print(row)

print("\n--- ORDERS ---")
for row in conn.execute("SELECT * FROM orders").fetchall():
    print(row)

conn.close()
