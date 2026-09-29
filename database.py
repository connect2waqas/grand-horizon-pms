"""
database.py - Database Architecture and Initialization
Hotel Management System MVP

This module manages the SQLite database lifecycle, schema migrations,
and initial data seeding. It enforces relational integrity and constraints.
"""

import datetime
import json
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

# Load environment variables from .env for local testing
load_dotenv()

# Locate local SQLite database file in the project root directory
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "hotel_management.db"

# Database URL and Engine configuration
def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        return f"sqlite:///{DATABASE_PATH}"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

IS_POSTGRES = bool(os.getenv("DATABASE_URL", "").startswith(("postgresql", "postgres")))

_engine = None

def get_engine():
    global _engine
    if _engine is not None:
        return _engine

    url = get_database_url()
    if url.startswith("postgresql"):
        import psycopg2.extras
        from sqlalchemy.pool import NullPool
        _engine = create_engine(url, poolclass=NullPool)
    else:
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return _engine


class CompatibleRow(dict):
    """
    Provides dual access by column name (like dict) and by integer index (like sqlite3.Row).
    Supports dict(rows) for 2-column key-value aggregations.
    Automatically coerces:
    - decimal.Decimal (PostgreSQL numeric types) to float
    - datetime.date (PostgreSQL date columns) to ISO-formatted str (matching SQLite TEXT dates)
    """
    def __init__(self, data: dict):
        cleaned = {}
        for k, v in data.items():
            if isinstance(v, Decimal):
                cleaned[k] = float(v)
            elif isinstance(v, datetime.date) and not isinstance(v, datetime.datetime):
                cleaned[k] = v.isoformat()
            else:
                cleaned[k] = v
        super().__init__(cleaned)
        self._values = list(cleaned.values())
        self._keys = list(cleaned.keys())

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._values[item]
        return super().__getitem__(item)

    def __iter__(self):
        if len(self._values) == 2:
            return iter((self._values[0], self._values[1]))
        return super().__iter__()

    def keys(self):
        return self._keys


class PostgresCursorWrapper:
    """
    Wraps psycopg2.extras.RealDictCursor to provide SQLite-compatible API:
    - Replaces '?' placeholders with '%s'
    - Translates SQLite date functions (date('now'), strftime) to PostgreSQL (CURRENT_DATE, to_char)
    - Automatically captures lastrowid on INSERT queries via RETURNING id
    - Returns CompatibleRow instances supporting both row['col'] and row[0]
    """
    def __init__(self, raw_cursor):
        self._cursor = raw_cursor
        self.lastrowid = None

    def execute(self, query: str, params=None):
        if params is not None:
            query = query.replace("?", "%s")

        # Translate SQLite-specific date syntax to PostgreSQL
        query = query.replace("date('now')", "CURRENT_DATE")
        query = query.replace('date("now")', "CURRENT_DATE")
        query = query.replace("datetime('now')", "CURRENT_TIMESTAMP")
        query = query.replace("strftime('%Y-%m', check_in_date)", "to_char(check_in_date, 'YYYY-MM')")
        query = query.replace("strftime('%Y-%m', 'now')", "to_char(CURRENT_DATE, 'YYYY-MM')")

        is_insert = query.strip().upper().startswith("INSERT")
        is_booking_amenities = "BOOKINGAMENITIES" in query.upper()
        if is_insert and "RETURNING" not in query.upper() and not is_booking_amenities:
            trimmed = query.rstrip().rstrip(";")
            returning_query = f"{trimmed} RETURNING id;"
            try:
                self._cursor.execute(returning_query, params)
                row = self._cursor.fetchone()
                if row and "id" in row:
                    self.lastrowid = row["id"]
                return self
            except Exception:
                pass

        self._cursor.execute(query, params)
        return self

    def executemany(self, query: str, params_list):
        query = query.replace("?", "%s")
        return self._cursor.executemany(query, params_list)

    def fetchone(self):
        row = self._cursor.fetchone()
        return CompatibleRow(row) if row is not None else None

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [CompatibleRow(r) for r in rows]

    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
        return [CompatibleRow(r) for r in rows]

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        return self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)


class PostgresConnectionWrapper:
    """
    Wraps raw SQLAlchemy psycopg2 connection to mimic sqlite3.Connection.
    """
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def cursor(self, *args, **kwargs):
        if "cursor_factory" not in kwargs:
            kwargs["cursor_factory"] = psycopg2.extras.RealDictCursor
        raw_cur = self._conn.cursor(*args, **kwargs)
        return PostgresCursorWrapper(raw_cur)

    def execute(self, query: str, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def get_db_connection():
    """
    Creates and returns a connection to the database.
    - If PostgreSQL (Supabase / Production): Uses SQLAlchemy connection pool with psycopg2 RealDictCursor
      for dictionary-like column name access and SQLite compatibility wrapper.
    - If SQLite (Local Development): Connects with row_factory=sqlite3.Row and PRAGMA foreign_keys=ON.
    """
    if IS_POSTGRES:
        conn = get_engine().raw_connection()
        return PostgresConnectionWrapper(conn)
    else:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn


def init_db() -> None:
    """
    Initializes the database schema with normalized tables and strict CHECK constraints:
    - Guests: Guest entity storing customer profile info
    - Rooms: Room inventory with room type and operational status constraints
    - Bookings: Relational junction entity linking Guests and Rooms with date validation
    """
    if IS_POSTGRES:
        print("Connected to PostgreSQL database. Schema is managed via Supabase migrations.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Table 1: Guests (Guest identity, VIP tiering, and preferences)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        vip_tier TEXT NOT NULL DEFAULT 'Standard' CHECK(vip_tier IN ('Standard', 'Silver', 'Gold', 'Platinum')),
        notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Schema migration: Ensure vip_tier and notes columns exist if database was previously created
    cursor.execute("PRAGMA table_info(Guests);")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "vip_tier" not in existing_cols:
        cursor.execute("ALTER TABLE Guests ADD COLUMN vip_tier TEXT NOT NULL DEFAULT 'Standard';")
    if "notes" not in existing_cols:
        cursor.execute("ALTER TABLE Guests ADD COLUMN notes TEXT DEFAULT '';")


    # Table 2: Rooms (Strict enum-like CHECK constraints on room_type and status)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT NOT NULL UNIQUE,
        room_type TEXT NOT NULL CHECK(room_type IN ('Single', 'Double', 'Family Suite')),
        price_per_night REAL NOT NULL CHECK(price_per_night > 0),
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance', 'Cleaning')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table 3: Bookings (Foreign Keys with referential integrity; checkout after checkin constraint)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_id INTEGER NOT NULL,
        room_id INTEGER NOT NULL,
        check_in_date DATE NOT NULL,
        check_out_date DATE NOT NULL,
        total_price REAL NOT NULL CHECK(total_price >= 0),
        booking_status TEXT NOT NULL DEFAULT 'Confirmed' CHECK(booking_status IN ('Confirmed', 'Checked-in', 'Checked-out', 'Cancelled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (guest_id) REFERENCES Guests(id) ON DELETE CASCADE,
        FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE RESTRICT,
        CHECK (check_out_date > check_in_date)
    );
    """)

    # Table 4: Amenities (Catalog of bookable hotel add-ons)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Amenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        price REAL NOT NULL CHECK(price >= 0),
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table 5: BookingAmenities (Many-to-Many junction linking Bookings and Amenities)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS BookingAmenities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        amenity_id INTEGER NOT NULL,
        price_charged REAL NOT NULL CHECK(price_charged >= 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES Bookings(id) ON DELETE CASCADE,
        FOREIGN KEY (amenity_id) REFERENCES Amenities(id) ON DELETE RESTRICT,
        UNIQUE(booking_id, amenity_id)
    );
    """)

    # Table 6: Coupons (Promotional discount coupon engine)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        discount_type TEXT NOT NULL CHECK(discount_type IN ('Percentage', 'FixedAmount')),
        discount_value REAL NOT NULL CHECK(discount_value > 0),
        valid_from DATE NOT NULL,
        valid_until DATE NOT NULL,
        min_total REAL NOT NULL DEFAULT 0.0 CHECK(min_total >= 0),
        max_uses INTEGER NOT NULL DEFAULT 100 CHECK(max_uses > 0),
        used_count INTEGER NOT NULL DEFAULT 0 CHECK(used_count >= 0),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK(valid_until >= valid_from)
    );
    """)

    # Schema migration: Ensure coupon_code and discount_amount exist on Bookings
    cursor.execute("PRAGMA table_info(Bookings);")
    booking_cols = {row[1] for row in cursor.fetchall()}
    if "coupon_code" not in booking_cols:
        cursor.execute("ALTER TABLE Bookings ADD COLUMN coupon_code TEXT DEFAULT NULL;")
    if "discount_amount" not in booking_cols:
        cursor.execute("ALTER TABLE Bookings ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0.0;")

    # Table 7: AuditLogs (Enterprise Operations Trail & Change Ledger)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS AuditLogs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL CHECK(entity_type IN ('Room', 'Booking', 'Guest', 'Coupon', 'System')),
        entity_id INTEGER,
        actor TEXT NOT NULL DEFAULT 'Front Desk Agent',
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Table 8: MaintenanceTickets (Work Orders & Facilities Task Management)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS MaintenanceTickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER NOT NULL,
        issue_description TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('Plumbing', 'Electrical', 'HVAC', 'Furniture', 'Sanitization', 'Structural', 'General')),
        priority TEXT NOT NULL CHECK(priority IN ('Low', 'Medium', 'High', 'Urgent')),
        status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open', 'In Progress', 'Resolved', 'Cancelled')),
        assigned_staff TEXT DEFAULT 'Facilities Team',
        reported_by TEXT DEFAULT 'Housekeeping',
        estimated_cost REAL DEFAULT 0.0,
        resolution_notes TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP DEFAULT NULL,
        FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE CASCADE
    );
    """)

    # Table 9: FolioCharges (Guest Ledger & Room Incidentals Billing)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS FolioCharges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        service_category TEXT NOT NULL CHECK(service_category IN ('Dining', 'Minibar', 'Spa', 'Parking', 'Laundry', 'Miscellaneous')),
        description TEXT NOT NULL,
        unit_price REAL NOT NULL CHECK(unit_price >= 0.0),
        quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
        total_price REAL NOT NULL CHECK(total_price >= 0.0),
        status TEXT NOT NULL DEFAULT 'Billed' CHECK(status IN ('Billed', 'Paid', 'Voided')),
        posted_by TEXT NOT NULL DEFAULT 'Front Desk Agent',
        void_reason TEXT DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (booking_id) REFERENCES Bookings(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
    print("Database tables initialized successfully with foreign key enforcement.")


def record_audit_log(
    conn: sqlite3.Connection,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    details: Optional[Any] = None,
    actor: str = "Front Desk Agent",
) -> int:
    """
    Appends an immutable audit event to the AuditLogs ledger.
    Accepts details either as a dict or string, serializing dicts to JSON.
    """
    if isinstance(details, dict):
        details_str = json.dumps(details)
    else:
        details_str = str(details) if details is not None else ""

    cursor = conn.cursor()
    if not IS_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS AuditLogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            actor TEXT NOT NULL DEFAULT 'Front Desk Agent',
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
    try:
        cursor.execute(
            """
            INSERT INTO AuditLogs (action, entity_type, entity_id, actor, details)
            VALUES (?, ?, ?, ?, ?);
            """,
            (action, entity_type, entity_id, actor, details_str),
        )
        return cursor.lastrowid or 0
    except Exception as exc:
        print(f"Audit log insertion notice: {exc}")
        return 0




def seed_amenities() -> None:
    """
    Seeds hotel amenities catalog (breakfast, shuttle, spa, valet, late checkout).
    Idempotent using INSERT OR IGNORE based on unique amenity name.
    """
    if IS_POSTGRES:
        return
    sample_amenities: List[Tuple[str, float, str]] = [
        ("Executive Breakfast", 24.99, "Daily full continental buffet with gourmet coffee"),
        ("Airport Shuttle Transfer", 35.00, "Private roundtrip airport transit service"),
        ("Spa & Thermal Suite Pass", 45.00, "All-day pass to hydrotherapy pools and sauna"),
        ("Late Checkout (2 PM)", 29.99, "Extended checkout privilege until 2:00 PM"),
        ("Valet Parking", 19.99, "Secure overnight valet parking with unlimited in/out access"),
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executemany(
        """
        INSERT OR IGNORE INTO Amenities (name, price, description)
        VALUES (?, ?, ?);
        """,
        sample_amenities,
    )
    conn.commit()

    cursor.execute("SELECT id, name, price FROM Amenities;")
    amenities = cursor.fetchall()
    conn.close()
    print(f"Amenities seeded. Total in catalog: {len(amenities)}")


def seed_rooms() -> None:
    """
    Seeds the database with initial rooms across all categories and realistic operational states.
    Uses INSERT OR IGNORE based on unique room_number to guarantee idempotency.
    """
    if IS_POSTGRES:
        return
    sample_rooms: List[Tuple[str, str, float, str]] = [
        ("101", "Single", 79.99, "Available"),
        ("102", "Single", 84.99, "Cleaning"),
        ("201", "Double", 129.99, "Available"),
        ("202", "Double", 139.99, "Occupied"),
        ("301", "Family Suite", 219.99, "Available"),
        ("302", "Family Suite", 249.99, "Available"),
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executemany(
        """
        INSERT OR IGNORE INTO Rooms (room_number, room_type, price_per_night, status)
        VALUES (?, ?, ?, ?);
        """,
        sample_rooms,
    )

    conn.commit()

    cursor.execute("SELECT id, room_number, room_type, price_per_night, status FROM Rooms;")
    rooms = cursor.fetchall()
    conn.close()

    print(f"Sample rooms seeded. Total rooms in database: {len(rooms)}")
    for room in rooms:
        print(f" - Room {room['room_number']} ({room['room_type']}): ${room['price_per_night']}/night [{room['status']}]")


def seed_coupons() -> None:
    """
    Seeds promotional discount coupons.
    Idempotent using INSERT OR IGNORE based on unique coupon code.
    """
    if IS_POSTGRES:
        return
    sample_coupons = [
        ("WELCOME10", "Percentage", 10.0, "2026-01-01", "2028-12-31", 100.0, 500, 0, 1),
        ("HORIZON25", "FixedAmount", 25.0, "2026-01-01", "2028-12-31", 150.0, 200, 0, 1),
        ("SUMMER20", "Percentage", 20.0, "2026-06-01", "2028-08-31", 250.0, 100, 0, 1),
        ("VIP50", "FixedAmount", 50.0, "2026-01-01", "2028-12-31", 300.0, 50, 0, 1),
    ]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT OR IGNORE INTO Coupons (code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, used_count, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        sample_coupons,
    )
    conn.commit()
    cursor.execute("SELECT id, code, discount_type, discount_value FROM Coupons;")
    coupons = cursor.fetchall()
    conn.close()
    print(f"Coupons seeded. Total in catalog: {len(coupons)}")


def seed_audit_logs() -> None:
    """
    Seeds initial system audit logs if table is empty.
    """
    if IS_POSTGRES:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM AuditLogs;")
    if cursor.fetchone()["cnt"] == 0:
        sample_logs = [
            ("SYSTEM_INIT", "System", 0, "System Admin", json.dumps({"message": "Grand Horizon PMS Database initialized with 3NF schema and foreign key constraints"})),
            ("ROOM_INVENTORY_SEEDED", "Room", 1, "System Admin", json.dumps({"rooms_count": 6, "amenities_count": 5})),
            ("COUPONS_SEEDED", "Coupon", 1, "System Admin", json.dumps({"active_vouchers": ["WELCOME10", "HORIZON25", "SUMMER20", "VIP50"]})),
        ]
        cursor.executemany(
            """
            INSERT INTO AuditLogs (action, entity_type, entity_id, actor, details)
            VALUES (?, ?, ?, ?, ?);
            """,
            sample_logs,
        )
        conn.commit()
        print("Audit logs initialized with bootstrap events.")
    conn.close()


def seed_maintenance_tickets() -> None:
    """
    Seeds initial maintenance work orders if table is empty.
    """
    if IS_POSTGRES:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM MaintenanceTickets;")
    if cursor.fetchone()["cnt"] == 0:
        sample_tickets = [
            (2, "Thermostat display flashing error code E-04", "HVAC", "Medium", "In Progress", "Marcus Cole (HVAC Lead)", "Housekeeping", 85.0, ""),
            (5, "Balcony sliding door latch sticky", "Structural", "Low", "Open", "Facilities Team", "Front Desk Agent", 45.0, ""),
        ]
        cursor.executemany(
            """
            INSERT INTO MaintenanceTickets (room_id, issue_description, category, priority, status, assigned_staff, reported_by, estimated_cost, resolution_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            sample_tickets,
        )
        conn.commit()
        print("Maintenance tickets seeded.")
    conn.close()


def seed_folio_charges() -> None:
    """
    Seeds initial incidental folio charges for active bookings if table is empty.
    """
    if IS_POSTGRES:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM FolioCharges;")
    if cursor.fetchone()["cnt"] == 0:
        # Check if booking 1 exists
        cursor.execute("SELECT id FROM Bookings LIMIT 1;")
        first_booking = cursor.fetchone()
        if first_booking:
            b_id = first_booking["id"]
            sample_charges = [
                (b_id, "Dining", "In-Room Dining: Artisan Wagyu Burger & Truffle Fries", 38.50, 1, 38.50, "Billed", "In-Room Dining Service", None),
                (b_id, "Minibar", "Sparkling Mineral Water & Gourmet Dark Chocolates", 14.00, 2, 28.00, "Billed", "Minibar Attendant", None),
            ]
            cursor.executemany(
                """
                INSERT INTO FolioCharges (booking_id, service_category, description, unit_price, quantity, total_price, status, posted_by, void_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                sample_charges,
            )
            conn.commit()
            print("Folio charges seeded.")
    conn.close()


if __name__ == "__main__":
    print(f"Target SQLite Database: {DATABASE_PATH}")
    init_db()
    seed_rooms()
    seed_amenities()
    seed_coupons()
    seed_audit_logs()
    seed_maintenance_tickets()
    seed_folio_charges()



