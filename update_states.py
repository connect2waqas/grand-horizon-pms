import sqlite3

def update_db():
    conn = sqlite3.connect('hotel_management.db')
    cur = conn.cursor()

    # Recreate or ensure CHECK allows Cleaning
    # SQLite 3.37+ allows disabling check or table recreation
    # Let's check table definition
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='Rooms';")
    sql = cur.fetchone()[0]
    if "'Cleaning'" not in sql:
        # Recreate table with new check constraint
        cur.execute("PRAGMA foreign_keys = OFF;")
        cur.execute("""
        CREATE TABLE Rooms_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL UNIQUE,
            room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Family Suite')),
            price_per_night REAL NOT NULL CHECK(price_per_night > 0),
            status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance', 'Cleaning')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cur.execute("INSERT INTO Rooms_new SELECT * FROM Rooms;")
        cur.execute("DROP TABLE Rooms;")
        cur.execute("ALTER TABLE Rooms_new RENAME TO Rooms;")
        cur.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

    # Insert room 302 if not present
    cur.execute("""
    INSERT OR IGNORE INTO Rooms (room_number, room_type, price_per_night, status)
    VALUES ('302', 'Family Suite', 249.99, 'Available');
    """)

    # Set dynamic statuses
    cur.execute("UPDATE Rooms SET status = 'Cleaning' WHERE room_number = '102';")
    cur.execute("UPDATE Rooms SET status = 'Occupied' WHERE room_number = '202';")

    # Ensure 202 has an active booking through 2026-10-04
    cur.execute("SELECT id FROM Rooms WHERE room_number = '202';")
    r202 = cur.fetchone()
    if r202:
        r202_id = r202[0]
        cur.execute("""
        INSERT INTO Bookings (guest_id, room_id, check_in_date, check_out_date, total_price, booking_status)
        VALUES (1, ?, '2026-09-28', '2026-10-04', 839.94, 'Confirmed');
        """, (r202_id,))

    conn.commit()
    conn.close()
    print("Database updated with dynamic operational states successfully!")

if __name__ == "__main__":
    update_db()
