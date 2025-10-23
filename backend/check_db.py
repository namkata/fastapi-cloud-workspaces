import sqlite3

# Connect to the database
conn = sqlite3.connect('app.db')
cursor = conn.cursor()

# Check what tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables in database:", tables)

# Check if users table exists and show its structure
if ('users',) in tables:
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("Users table structure:", columns)

    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()
    print("Number of users:", count[0])
else:
    print("Users table does not exist")

conn.close()
