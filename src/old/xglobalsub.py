import sqlite3, os

depot_local = os.getenv('DEPOT_ALL')
#path_base_photo = os.path.join(depot_local, 'assetdepot', 'photo', 'people', 'ig')
path_base_photo = os.path.join(depot_local, 'assetdepot', 'photo')
path_db_photo = os.path.join(path_base_photo, 'db') 
file_sqlite_media = 'db_media.sqlite3'
path_db_media = os.path.join(path_db_photo, file_sqlite_media)

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect(path_db_media)
cursor = conn.cursor()


# Perform string substitution in 'path'
# Replace all occurrences of 'World' with 'Universe'
cursor.execute("UPDATE media SET path = REPLACE(path, 'assetdepot/photo', 'assetdepot/media')")


# Commit the changes
conn.commit()

# Verify the changes
#cursor.execute("SELECT * FROM my_table")
# fetch the first 10 rows
cursor.execute("SELECT * FROM media LIMIT 10")
rows = cursor.fetchall()
for row in rows:
    print(row)

# Close the connection
conn.close()