"""
verify_db.py - Verification script for database architecture and constraints.
"""
import sqlite3
from database import get_db_connection

def verify() -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Verify Seeded Rooms
    cur.execute("SELECT COUNT(*) FROM Rooms;")
    count = cur.fetchone()[0]
    assert count == 5, f"Expected 5 seeded rooms, found {count}"
    print(f"[PASS] 5 seeded rooms verified.")

    # 2. Verify CHECK constraint on room_type
    try:
        cur.execute(
            "INSERT INTO Rooms (room_number, room_type, price_per_night) VALUES ('999', 'Penthouse', 500);"
        )
        conn.commit()
        raise AssertionError("CHECK constraint failed to reject invalid room_type 'Penthouse'")
    except sqlite3.IntegrityError:
        print("[PASS] CHECK constraint rejected invalid room_type ('Penthouse').")

    # 3. Verify Foreign Key constraint on guest_id
    try:
        cur.execute(
            "INSERT INTO Bookings (guest_id, room_id, check_in_date, check_out_date, total_price) "
            "VALUES (9999, 1, '2026-10-01', '2026-10-05', 300.0);"
        )
        conn.commit()
        raise AssertionError("Foreign key constraint failed to reject non-existent guest_id 9999")
    except sqlite3.IntegrityError:
        print("[PASS] Foreign key enforcement rejected invalid guest_id (9999).")

    # 4. Verify check_out_date > check_in_date constraint
    try:
        # First insert a valid guest
        cur.execute(
            "INSERT INTO Guests (first_name, last_name, email, phone) "
            "VALUES ('Test', 'User', 'test@example.com', '1234567890');"
        )
        guest_id = cur.lastrowid
        cur.execute(
            "INSERT INTO Bookings (guest_id, room_id, check_in_date, check_out_date, total_price) "
            f"VALUES ({guest_id}, 1, '2026-10-05', '2026-10-01', 300.0);"
        )
        conn.commit()
        raise AssertionError("CHECK constraint failed to reject check_out_date <= check_in_date")
    except sqlite3.IntegrityError:
        print("[PASS] Date validity constraint rejected invalid date range (checkout earlier than checkin).")

    conn.rollback()
    conn.close()
    print("\nAll database constraints and foreign keys verified successfully!")

if __name__ == "__main__":
    verify()
