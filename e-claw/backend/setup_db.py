import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Connect to PostgreSQL
conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='postgres'
)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()

# Create user
try:
    cur.execute("CREATE USER eclaw WITH PASSWORD 'eclaw'")
    print("User 'eclaw' created")
except Exception as e:
    print(f"User creation: {e}")

# Create database
try:
    cur.execute("CREATE DATABASE eclaw OWNER eclaw")
    print("Database 'eclaw' created")
except Exception as e:
    print(f"Database creation: {e}")

# Grant privileges
try:
    cur.execute("GRANT ALL PRIVILEGES ON DATABASE eclaw TO eclaw")
    print("Privileges granted")
except Exception as e:
    print(f"Grant privileges: {e}")

cur.close()
conn.close()
print("Done!")