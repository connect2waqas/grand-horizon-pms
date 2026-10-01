-- ==============================================================================
-- Grand Horizon Hotel Management System - Supabase (PostgreSQL) Migration Script
-- Target: Supabase SQL Editor / PostgreSQL 15+
-- ==============================================================================

-- Explicitly ensure public schema context
SET search_path TO public;

-- ------------------------------------------------------------------------------
-- 1. Table: guests (CRM, Guest Profiles & Loyalty Tiering)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.guests (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50) NOT NULL,
    vip_tier VARCHAR(20) NOT NULL DEFAULT 'Standard' CHECK (vip_tier IN ('Standard', 'Silver', 'Gold', 'Platinum')),
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 2. Table: rooms (Accommodations Inventory & Operational State)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.rooms (
    id SERIAL PRIMARY KEY,
    room_number VARCHAR(20) NOT NULL UNIQUE,
    room_type VARCHAR(50) NOT NULL CHECK (room_type IN ('Single', 'Double', 'Family Suite')),
    price_per_night NUMERIC(10, 2) NOT NULL CHECK (price_per_night > 0),
    status VARCHAR(30) NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'Occupied', 'Cleaning', 'Maintenance')),
    floor INTEGER NOT NULL DEFAULT 1,
    max_occupancy INTEGER NOT NULL DEFAULT 2,
    bed_type VARCHAR(100) NOT NULL DEFAULT '1 King Bed',
    view_type VARCHAR(100) NOT NULL DEFAULT 'City Skyline',
    sq_meters INTEGER NOT NULL DEFAULT 35,
    is_smoking BOOLEAN NOT NULL DEFAULT FALSE,
    cleanliness_status VARCHAR(50) NOT NULL DEFAULT 'Inspected' CHECK (cleanliness_status IN ('Clean', 'Dirty', 'Inspected', 'Touch-up Required')),
    lock_reason TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Schema migration columns for existing Supabase installations
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS floor INTEGER NOT NULL DEFAULT 1;
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS max_occupancy INTEGER NOT NULL DEFAULT 2;
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS bed_type VARCHAR(100) NOT NULL DEFAULT '1 King Bed';
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS view_type VARCHAR(100) NOT NULL DEFAULT 'City Skyline';
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS sq_meters INTEGER NOT NULL DEFAULT 35;
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS is_smoking BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS cleanliness_status VARCHAR(50) NOT NULL DEFAULT 'Inspected';
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS lock_reason TEXT DEFAULT NULL;

-- ------------------------------------------------------------------------------
-- 3. Table: amenities (Add-On Guest Services Catalog)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.amenities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 4. Table: coupons (Promotional Rate Engine & Voucher Management)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.coupons (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    discount_type VARCHAR(30) NOT NULL CHECK (discount_type IN ('Percentage', 'FixedAmount')),
    discount_value NUMERIC(10, 2) NOT NULL CHECK (discount_value > 0),
    valid_from DATE NOT NULL,
    valid_until DATE NOT NULL,
    min_total NUMERIC(10, 2) NOT NULL DEFAULT 0.0 CHECK (min_total >= 0),
    max_uses INTEGER NOT NULL DEFAULT 100 CHECK (max_uses > 0),
    used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 5. Table: bookings (Reservations, Folio Lifecycle & Rates)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.bookings (
    id SERIAL PRIMARY KEY,
    guest_id INTEGER NOT NULL REFERENCES public.guests(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES public.rooms(id) ON DELETE CASCADE,
    check_in_date DATE NOT NULL,
    check_out_date DATE NOT NULL,
    total_price NUMERIC(10, 2) NOT NULL CHECK (total_price >= 0),
    booking_status VARCHAR(30) NOT NULL DEFAULT 'Confirmed' CHECK (booking_status IN ('Confirmed', 'Checked-in', 'Checked-out', 'Cancelled')),
    coupon_code VARCHAR(50) DEFAULT NULL,
    discount_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.0 CHECK (discount_amount >= 0),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_dates_validity CHECK (check_out_date > check_in_date)
);

-- Schema migration columns for existing Supabase installations (Module 2 Deepening)
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS adults INTEGER NOT NULL DEFAULT 1;
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS children INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS estimated_arrival_time VARCHAR(20) DEFAULT '15:00';
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS special_requests TEXT DEFAULT '';
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS guarantee_type VARCHAR(30) NOT NULL DEFAULT 'Guaranteed';
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS early_checkin_requested BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS late_checkout_requested BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS rate_plan_code VARCHAR(30) NOT NULL DEFAULT 'BAR';

-- ------------------------------------------------------------------------------
-- 5b. Table: rateplans (Module 3: Enterprise Rate Plans & Dynamic Yield Controls)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.rateplans (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT DEFAULT '',
    rate_multiplier NUMERIC NOT NULL DEFAULT 1.0 CHECK (rate_multiplier > 0),
    cancellation_policy VARCHAR(100) NOT NULL DEFAULT 'Flexible (24h free cancellation)',
    meal_plan VARCHAR(100) NOT NULL DEFAULT 'Room Only',
    min_los INTEGER NOT NULL DEFAULT 1 CHECK (min_los >= 1),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 6. Table: bookingamenities (Many-to-Many Junction for Pre-Booked Amenities)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.bookingamenities (
    booking_id INTEGER NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
    amenity_id INTEGER NOT NULL REFERENCES public.amenities(id) ON DELETE RESTRICT,
    price_charged NUMERIC(10, 2) NOT NULL CHECK (price_charged >= 0),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (booking_id, amenity_id)
);

-- ------------------------------------------------------------------------------
-- 7. Table: auditlogs (Enterprise Operations Trail & Change Ledger)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.auditlogs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('Room', 'Booking', 'Guest', 'Coupon', 'System')),
    entity_id INTEGER,
    actor VARCHAR(100) NOT NULL DEFAULT 'Front Desk Agent',
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 8. Table: maintenancetickets (Work Orders & Facilities Task Management)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.maintenancetickets (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES public.rooms(id) ON DELETE CASCADE,
    issue_description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('Plumbing', 'Electrical', 'HVAC', 'Furniture', 'Sanitization', 'Structural', 'General')),
    priority VARCHAR(20) NOT NULL CHECK (priority IN ('Low', 'Medium', 'High', 'Urgent')),
    status VARCHAR(30) NOT NULL DEFAULT 'Open' CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Cancelled')),
    assigned_staff VARCHAR(100) DEFAULT 'Facilities Team',
    reported_by VARCHAR(100) DEFAULT 'Housekeeping',
    estimated_cost NUMERIC(10, 2) DEFAULT 0.0 CHECK (estimated_cost >= 0),
    resolution_notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ DEFAULT NULL
);

-- ------------------------------------------------------------------------------
-- 9. Table: foliocharges (Guest Ledger & Room Incidentals Billing)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.foliocharges (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
    service_category VARCHAR(50) NOT NULL CHECK (service_category IN ('Dining', 'Minibar', 'Spa', 'Parking', 'Laundry', 'Miscellaneous')),
    description TEXT NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0.0),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    total_price NUMERIC(10, 2) NOT NULL CHECK (total_price >= 0.0),
    status VARCHAR(20) NOT NULL DEFAULT 'Billed' CHECK (status IN ('Billed', 'Paid', 'Voided')),
    posted_by VARCHAR(100) NOT NULL DEFAULT 'Front Desk Agent',
    void_reason TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- Row Level Security (RLS) Enforcement
-- ==============================================================================
ALTER TABLE public.guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.amenities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coupons ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookingamenities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auditlogs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.maintenancetickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.foliocharges ENABLE ROW LEVEL SECURITY;

-- ==============================================================================
-- Performance Indexes
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_bookings_overlap ON public.bookings (room_id, check_in_date, check_out_date);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON public.bookings (booking_status);
CREATE INDEX IF NOT EXISTS idx_rooms_status ON public.rooms (status);
CREATE INDEX IF NOT EXISTS idx_guests_email ON public.guests (email);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON public.auditlogs (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_room_status ON public.maintenancetickets (room_id, status);
CREATE INDEX IF NOT EXISTS idx_folio_booking_status ON public.foliocharges (booking_id, status);

-- ==============================================================================
-- Idempotent Seed Data Initialization
-- ==============================================================================

-- 1. Initial Room Catalog
INSERT INTO public.rooms (room_number, room_type, price_per_night, status) VALUES
('101', 'Single', 79.99, 'Available'),
('102', 'Single', 84.99, 'Available'),
('201', 'Double', 129.99, 'Occupied'),
('202', 'Double', 139.99, 'Occupied'),
('301', 'Family Suite', 219.99, 'Occupied'),
('302', 'Family Suite', 249.99, 'Available')
ON CONFLICT (room_number) DO NOTHING;

-- 2. Amenities Catalog
INSERT INTO public.amenities (name, price, description) VALUES
('Executive Breakfast', 24.99, 'Daily full continental buffet with gourmet coffee'),
('Airport Shuttle Transfer', 35.00, 'Private roundtrip airport transit service'),
('Spa & Thermal Suite Pass', 45.00, 'All-day pass to hydrotherapy pools and sauna'),
('Late Checkout (2 PM)', 29.99, 'Extended checkout privilege until 2:00 PM'),
('Valet Parking', 19.99, 'Secure overnight valet parking with unlimited in/out access')
ON CONFLICT (name) DO NOTHING;

-- 3. Promotional Coupons
INSERT INTO public.coupons (code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, is_active) VALUES
('WELCOME10', 'Percentage', 10.0, '2026-01-01', '2026-12-31', 50.0, 500, TRUE),
('HORIZON25', 'FixedAmount', 25.0, '2026-01-01', '2026-12-31', 150.0, 200, TRUE),
('SUMMER20', 'Percentage', 20.0, '2026-06-01', '2026-08-31', 200.0, 150, TRUE),
('VIP50', 'FixedAmount', 50.0, '2026-01-01', '2026-12-31', 300.0, 100, TRUE)
ON CONFLICT (code) DO NOTHING;

-- 4. Initial Bootstrap Audit Event
INSERT INTO public.auditlogs (action, entity_type, entity_id, actor, details) VALUES
('SYSTEM_MIGRATED', 'System', 1, 'DevOps Lead', '{"database": "Supabase PostgreSQL", "environment": "Production"}');

-- 5. Rate Plans Catalog (Module 3)
INSERT INTO public.rateplans (code, name, description, rate_multiplier, cancellation_policy, meal_plan, min_los, is_active) VALUES
('BAR', 'Best Available Rate', 'Standard fully flexible rate with 24-hour cancellation flexibility.', 1.0, 'Flexible (24h free cancellation)', 'Room Only', 1, TRUE),
('NON_REF', 'Non-Refundable Saver', 'Advance purchase saver plan with guaranteed 15% discount. 100% non-refundable.', 0.85, 'Non-Refundable (100% deposit locked)', 'Room Only', 1, TRUE),
('BB_PACKAGE', 'Bed & Breakfast Package', 'Includes gourmet daily continental breakfast buffet for all guests.', 1.15, 'Flexible (24h free cancellation)', 'Continental Breakfast Included', 1, TRUE),
('CORP_EXTENDED', 'Extended Stay & Corporate', 'Long-stay executive preferred partner pricing with 20% discount. Minimum 3 nights required.', 0.80, 'Moderate (48h cancellation)', 'Room Only', 3, TRUE)
ON CONFLICT (code) DO NOTHING;

-- ==============================================================================
-- Module 4: Housekeeping & Room Status Management
-- ==============================================================================

-- Alter Rooms table for Housekeeping Deepening
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS assigned_housekeeper VARCHAR(100) DEFAULT NULL;
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS cleaning_priority VARCHAR(50) NOT NULL DEFAULT 'Normal';
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS dnd_status INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS last_cleaned_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE public.rooms ADD COLUMN IF NOT EXISTS last_inspected_at TIMESTAMPTZ DEFAULT NULL;

-- Table 10: HousekeepingTasks (Turnover, Cleaning, and Quality Inspections)
CREATE TABLE IF NOT EXISTS public.housekeepingtasks (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES public.rooms(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL DEFAULT 'Checkout Turnover',
    priority VARCHAR(50) NOT NULL DEFAULT 'Normal',
    status VARCHAR(50) NOT NULL DEFAULT 'Pending',
    assigned_housekeeper VARCHAR(100) DEFAULT 'Maria Santos',
    linen_changed INTEGER NOT NULL DEFAULT 0,
    amenities_restocked INTEGER NOT NULL DEFAULT 0,
    bathroom_sanitized INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    inspected_by VARCHAR(100) DEFAULT NULL,
    inspector_notes TEXT DEFAULT '',
    started_at TIMESTAMPTZ DEFAULT NULL,
    completed_at TIMESTAMPTZ DEFAULT NULL,
    inspected_at TIMESTAMPTZ DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_housekeeping_room_status ON public.housekeepingtasks (room_id, status);
CREATE INDEX IF NOT EXISTS idx_housekeeping_housekeeper ON public.housekeepingtasks (assigned_housekeeper);

-- 6. Initial Housekeeping Tasks Seed Data
INSERT INTO public.housekeepingtasks (room_id, task_type, priority, status, assigned_housekeeper, linen_changed, amenities_restocked, bathroom_sanitized, notes) VALUES
(3, 'Checkout Turnover', 'Rush Checkout Turnover', 'Pending', 'Maria Santos', 0, 0, 0, 'Previous guest departed at 11 AM. New check-in expected at 3 PM.'),
(4, 'Stayover Clean', 'Normal', 'In Progress', 'David Kim', 1, 0, 0, 'Replace extra towels and restock espresso pods.'),
(1, 'Inspection Audit', 'Normal', 'Inspected', 'Elena Rostova', 1, 1, 1, 'Passed 5-star quality sanitation audit.')
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- Module 5: Room Keycard / Access Control & Security Logging
-- ==============================================================================

-- Table 11: keycards (RFID / NFC Credentials & Access Permissions)
CREATE TABLE IF NOT EXISTS public.keycards (
    id SERIAL PRIMARY KEY,
    card_uid VARCHAR(100) NOT NULL UNIQUE,
    room_id INTEGER REFERENCES public.rooms(id) ON DELETE SET NULL,
    booking_id INTEGER REFERENCES public.bookings(id) ON DELETE SET NULL,
    holder_name VARCHAR(150) NOT NULL,
    card_type VARCHAR(50) NOT NULL DEFAULT 'Guest',
    status VARCHAR(50) NOT NULL DEFAULT 'Active',
    issued_by VARCHAR(100) NOT NULL DEFAULT 'Front Desk Encoder',
    notes TEXT DEFAULT '',
    issued_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ DEFAULT NULL,
    revoked_at TIMESTAMPTZ DEFAULT NULL,
    revoked_reason VARCHAR(255) DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_keycards_card_uid ON public.keycards (card_uid);
CREATE INDEX IF NOT EXISTS idx_keycards_room_id ON public.keycards (room_id);
CREATE INDEX IF NOT EXISTS idx_keycards_booking_id ON public.keycards (booking_id);
CREATE INDEX IF NOT EXISTS idx_keycards_status ON public.keycards (status);

-- Table 12: accesslogs (Electronic Reader Door Taps & Audit Trail)
CREATE TABLE IF NOT EXISTS public.accesslogs (
    id SERIAL PRIMARY KEY,
    card_uid VARCHAR(100) NOT NULL,
    room_id INTEGER NOT NULL REFERENCES public.rooms(id) ON DELETE CASCADE,
    reader_location VARCHAR(150) NOT NULL DEFAULT 'Room Exterior Lock',
    event_type VARCHAR(50) NOT NULL,
    access_granted BOOLEAN NOT NULL DEFAULT FALSE,
    attempted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accesslogs_room_id ON public.accesslogs (room_id);
CREATE INDEX IF NOT EXISTS idx_accesslogs_card_uid ON public.accesslogs (card_uid);
CREATE INDEX IF NOT EXISTS idx_accesslogs_attempted_at ON public.accesslogs (attempted_at DESC);

-- 7. Initial Keycards Seed Data
INSERT INTO public.keycards (card_uid, room_id, booking_id, holder_name, card_type, status, issued_by, notes, expires_at, revoked_at, revoked_reason) VALUES
('RFID-101A-8821', 1, 1, 'Alexander Pierce', 'Guest', 'Active', 'Front Desk Encoder', 'Primary guest keycard', NULL, NULL, NULL),
('RFID-201A-4432', 3, 2, 'Sophia Laurent', 'Guest', 'Active', 'Front Desk Encoder', 'Primary guest keycard', NULL, NULL, NULL),
('RFID-MASTER-001', NULL, NULL, 'Sarah Jenkins (GM)', 'Staff Master', 'Active', 'Security Admin', 'Master bypass key for Executive General Manager', NULL, NULL, NULL),
('RFID-HK-002', NULL, NULL, 'Maria Santos', 'Housekeeping', 'Active', 'Housekeeping Supervisor', 'Attendant floor service key', NULL, NULL, NULL),
('RFID-101A-7700', 1, 1, 'Alexander Pierce', 'Guest', 'Revoked', 'Front Desk Encoder', 'Old keycard replaced due to misplacement', '2026-09-29 14:00:00+00', '2026-09-29 18:30:00+00', 'Reported Lost by Guest; Replaced with RFID-101A-8821')
ON CONFLICT (card_uid) DO NOTHING;

-- 8. Initial Access Logs Seed Data
INSERT INTO public.accesslogs (card_uid, room_id, reader_location, event_type, access_granted, attempted_at) VALUES
('RFID-101A-8821', 1, 'Room 101 Exterior Lock', 'Granted', TRUE, '2026-10-01 10:15:00+00'),
('RFID-MASTER-001', 2, 'Room 102 Exterior Lock', 'Granted', TRUE, '2026-10-01 11:30:00+00'),
('RFID-101A-7700', 1, 'Room 101 Exterior Lock', 'Denied - Card Revoked', FALSE, '2026-10-01 11:45:00+00'),
('RFID-101A-8821', 2, 'Room 102 Exterior Lock', 'Denied - Invalid Room', FALSE, '2026-10-01 12:00:00+00')
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- Module 6: Multi-Currency & International Tax Engine
-- ==============================================================================

-- Table 13: exchangerates (Forex Conversion Rates Against Base USD)
CREATE TABLE IF NOT EXISTS public.exchangerates (
    currency_code VARCHAR(3) PRIMARY KEY,
    currency_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    rate_to_usd NUMERIC(10, 4) NOT NULL CHECK (rate_to_usd > 0),
    is_base BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exchangerates_is_base ON public.exchangerates (is_base);

-- Table 14: taxrules (Statutory Hotel Taxes & Municipal Surcharges)
CREATE TABLE IF NOT EXISTS public.taxrules (
    id SERIAL PRIMARY KEY,
    tax_name VARCHAR(100) NOT NULL,
    tax_type VARCHAR(50) NOT NULL DEFAULT 'Percentage',
    rate NUMERIC(10, 2) NOT NULL CHECK (rate >= 0),
    currency_code VARCHAR(3) NOT NULL DEFAULT 'USD',
    applies_to VARCHAR(50) NOT NULL DEFAULT 'All',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_taxrules_active ON public.taxrules (is_active);

-- Enable RLS
ALTER TABLE public.exchangerates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.taxrules ENABLE ROW LEVEL SECURITY;

-- 9. Initial Exchange Rates Seed Data
INSERT INTO public.exchangerates (currency_code, currency_name, symbol, rate_to_usd, is_base) VALUES
('USD', 'US Dollar', '$', 1.0000, TRUE),
('EUR', 'Euro', '€', 0.9200, FALSE),
('GBP', 'British Pound', '£', 0.7900, FALSE),
('JPY', 'Japanese Yen', '¥', 152.5000, FALSE),
('CAD', 'Canadian Dollar', 'C$', 1.3800, FALSE),
('AUD', 'Australian Dollar', 'A$', 1.5200, FALSE),
('CHF', 'Swiss Franc', 'CHF', 0.8800, FALSE)
ON CONFLICT (currency_code) DO NOTHING;

-- 10. Initial Statutory Tax Rules Seed Data
INSERT INTO public.taxrules (tax_name, tax_type, rate, currency_code, applies_to, is_active) VALUES
('Standard Occupancy Sales Tax / VAT', 'Percentage', 10.00, 'USD', 'All', TRUE),
('City Tourism Municipal Surcharge', 'Flat_Per_Night', 5.00, 'USD', 'Room_Only', TRUE),
('Eco Sustainability & Green Resort Levy', 'Flat_Per_Stay', 12.00, 'USD', 'All', TRUE)
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- Module 7: Advanced Room Operations, Out-of-Order (OOO) & Guest Relocation Engine
-- ==============================================================================

-- Table 15: roomlockouts (Out-of-Order and Out-of-Service Management)
CREATE TABLE IF NOT EXISTS public.roomlockouts (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES public.rooms (id) ON DELETE CASCADE,
    lockout_type VARCHAR(50) NOT NULL DEFAULT 'Out_of_Order',
    reason VARCHAR(255) NOT NULL,
    assigned_trade VARCHAR(100) DEFAULT 'General Maintenance',
    expected_completion VARCHAR(50) DEFAULT NULL,
    authorized_by VARCHAR(100) NOT NULL DEFAULT 'Duty Manager',
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ DEFAULT NULL,
    resolved_by VARCHAR(100) DEFAULT NULL,
    resolution_notes TEXT DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_room_lockouts_active ON public.roomlockouts (room_id, is_active);

-- Table 16: roommoves (Guest Emergency Relocation Ledger)
CREATE TABLE IF NOT EXISTS public.roommoves (
    id SERIAL PRIMARY KEY,
    booking_id INTEGER NOT NULL REFERENCES public.bookings (id) ON DELETE CASCADE,
    old_room_id INTEGER NOT NULL REFERENCES public.rooms (id) ON DELETE CASCADE,
    new_room_id INTEGER NOT NULL REFERENCES public.rooms (id) ON DELETE CASCADE,
    reason VARCHAR(255) NOT NULL,
    relocated_by VARCHAR(100) NOT NULL DEFAULT 'Front Desk Duty Manager',
    keycards_reassigned INTEGER NOT NULL DEFAULT 0,
    relocated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_room_moves_booking ON public.roommoves (booking_id);

-- Enable RLS
ALTER TABLE public.roomlockouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.roommoves ENABLE ROW LEVEL SECURITY;

-- 11. Initial Room Lockouts & Moves Seed Data
INSERT INTO public.roomlockouts (room_id, lockout_type, reason, assigned_trade, expected_completion, authorized_by, notes, resolved_at, resolved_by, resolution_notes, is_active) VALUES
(2, 'Out_of_Order', 'HVAC compressor replacement and duct sanitization', 'HVAC Mechanicals', '2026-09-25 18:00:00+00', 'Duty Manager', 'Compressor valve failure resolved', '2026-09-26 10:00:00+00', 'Lead Technician', 'New compressor certified and tested', FALSE)
ON CONFLICT DO NOTHING;

INSERT INTO public.roommoves (booking_id, old_room_id, new_room_id, reason, relocated_by, keycards_reassigned, relocated_at) VALUES
(1, 2, 1, 'In-room climate control system malfunction on arrival', 'Front Desk Duty Manager', 1, '2026-09-29 15:30:00+00')
ON CONFLICT DO NOTHING;



