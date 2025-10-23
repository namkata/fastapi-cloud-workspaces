import sqlite3

# Check fastapi_db.sqlite
print("=== Checking fastapi_db.sqlite ===")
try:
    conn = sqlite3.connect('fastapi_db.sqlite')
    cursor = conn.cursor()

    # Check what tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables in fastapi_db.sqlite:", tables)

    # Check if users table exists and show its data
    if ('users',) in tables:
        cursor.execute("SELECT email, username, is_active FROM users")
        users = cursor.fetchall()
        print("Users in fastapi_db.sqlite:", users)

    conn.close()
except Exception as e:
    print(f"Error checking fastapi_db.sqlite: {e}")

print("\n=== Checking app.db ===")
try:
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # Check what tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables in app.db:", tables)

    # Check if users table exists and show its data
    if ('users',) in tables:
        cursor.execute("SELECT email, username, is_active FROM users")
        users = cursor.fetchall()
        print("Users in app.db:", users)

    conn.close()
except Exception as e:
    print(f"Error checking app.db: {e}")
