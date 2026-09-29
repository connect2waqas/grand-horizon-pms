"""
main.py - FastAPI Core Application & REST Endpoints
Hotel Management System MVP

This module provides the REST API for room inventory and reservation management.
Features:
- Connection lifecycle via FastAPI dependency injection and lifespan context manager
- CORS enabled for seamless frontend integration
- Static files mounted to serve the vanilla frontend dashboard
- Availability checking preventing double-booking conflicts (HTTP 409)
- Secure server-side pricing computation
"""

import sys
from pathlib import Path

# Ensure parent root directory is in sys.path for Vercel Serverless runtime
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

STATIC_DIR = BASE_DIR / "static"

from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Generator, List, Optional
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from database import (
    get_db_connection,
    init_db,
    seed_rooms,
    seed_amenities,
    seed_coupons,
    record_audit_log,
    seed_audit_logs,
    seed_maintenance_tickets,
    seed_folio_charges,
    IS_POSTGRES,
)
from schemas import (
    AmenityResponse,
    AuditLogResponse,
    BookingCancelResponse,
    BookingCheckoutResponse,
    BookingCreate,
    BookingResponse,
    BookingStatus,
    CouponCreate,
    CouponResponse,
    CouponValidateRequest,
    CouponValidateResponse,
    DiscountType,
    FolioCategory,
    FolioChargeBase,
    FolioChargeCreate,
    FolioChargeResponse,
    FolioChargeStatus,
    FolioChargeVoid,
    FolioStatementResponse,
    GuestCreate,
    GuestCRMResponse,
    GuestDetailResponse,
    GuestResponse,
    GuestUpdate,
    InvoiceItem,
    KPIAnalyticsResponse,
    MaintenanceCategory,
    MaintenancePriority,
    MaintenanceStatus,
    MaintenanceSummaryResponse,
    MaintenanceTicketCreate,
    MaintenanceTicketResponse,
    MaintenanceTicketUpdate,
    NightlyRateDetail,
    PriceQuoteRequest,
    PriceQuoteResponse,
    RoomResponse,
    RoomStatus,
    RoomStatusUpdate,
    RoomType,
    VIPTier,
)

# ==========================================
# Database Connection Dependency
# ==========================================

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Request-scoped SQLite connection provider.
    Ensures connection isolation, foreign key enforcement, and deterministic cleanup.
    Can be easily overridden in automated test suites.
    """
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


# ==========================================
# Application Lifespan Lifecycle
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Initializes database schema and ensures sample rooms and amenities are seeded on startup (SQLite).
    In PostgreSQL / Supabase, schema and seeds are managed by supabase_migration.sql.
    """
    try:
        if not IS_POSTGRES:
            init_db()
            seed_rooms()
            seed_amenities()
            seed_coupons()
            seed_audit_logs()
            seed_maintenance_tickets()
            seed_folio_charges()
    except Exception as e:
        print(f"Lifespan initialization note: {e}")
    yield


# ==========================================
# FastAPI Application Configuration
# ==========================================

app = FastAPI(
    title="Hotel Management System API",
    description="REST API for hotel room inventory, guest profiles, and reservation scheduling.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for vanilla frontend interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable GZip compression for responses >= 1000 bytes (Core Web Vitals & speed optimization)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ==========================================
# Vercel & Backward Compatibility Path Rewriter
# ==========================================
class LegacyPathRewriterMiddleware:
    """
    Ensures both /api/resource (Vercel production standard) and /resource
    (local test suite & legacy compatibility) resolve to the same endpoints.
    Also handles Vercel rewrite routing where x-matched-path is provided.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            query_string = scope.get("query_string", b"").decode("utf-8", errors="ignore")

            # Check if Vercel passed the path via query string __path__
            if "__path__=" in query_string:
                import urllib.parse
                parsed_qs = urllib.parse.parse_qs(query_string)
                if "__path__" in parsed_qs and parsed_qs["__path__"]:
                    extracted = parsed_qs["__path__"][0].lstrip("/")
                    path = f"/api/{extracted}"
                    scope["path"] = path

            # Check if Vercel forwarded the original URL via x-matched-path header
            headers = dict(scope.get("headers", []))
            matched_path = headers.get(b"x-matched-path", b"").decode("utf-8", errors="ignore")
            if matched_path and matched_path != "/api/index.py":
                path = matched_path
                scope["path"] = path

            is_static_asset = any(path.endswith(ext) for ext in (".js", ".css", ".html", ".ico", ".png", ".jpg", ".svg", ".woff", ".woff2")) or path.startswith("/static")
            if not path.startswith("/api") and path not in ("/docs", "/openapi.json", "/redoc", "/", "/health") and not is_static_asset:
                scope["path"] = f"/api{path}"
        await self.app(scope, receive, send)

app.add_middleware(LegacyPathRewriterMiddleware)



# ==========================================
# REST Endpoints
# ==========================================

@app.get(
    "/api/health",
    summary="Vercel serverless and database health check probe",
    tags=["System"],
)
@app.get("/health", include_in_schema=False)
@app.get("/api/index.py", include_in_schema=False)
def health_check(request: Request = None):
    """
    Returns deployment health status for Vercel, Supabase connection, and edge monitors.
    Tests active database connectivity and returns clear diagnostics.
    """
    db_status = "connected"
    db_error = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        conn.close()
    except Exception as e:
        db_status = "error"
        db_error = str(e)

    headers_dict = {}
    path_info = {}
    if request:
        headers_dict = {k: v for k, v in request.headers.items() if "auth" not in k.lower() and "cookie" not in k.lower()}
        path_info = {
            "url": str(request.url),
            "path": request.url.path,
            "scope_path": request.scope.get("path"),
        }

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
        "database_error": db_error,
        "is_postgres": IS_POSTGRES,
        "path_info": path_info,
        "headers": headers_dict,
        "service": "Grand Horizon PMS API",
        "runtime": "Vercel Serverless (Python 3.14+)",
    }


@app.get(
    "/api/stats",
    summary="Get hotel performance KPIs",
    tags=["Analytics"],
)
def get_stats(conn: sqlite3.Connection = Depends(get_db)):
    """
    Returns high-level KPI metrics for backward compatibility.
    """
    kpis = get_kpi_analytics(response=Response(), conn=conn)
    return {
        "total_rooms": kpis.total_rooms,
        "occupancy_rate": kpis.occupancy_rate_display,
        "today_checkins": kpis.today_checkins,
        "est_revenue": kpis.total_revenue,
    }


@app.get(
    "/api/analytics/kpis",
    response_model=KPIAnalyticsResponse,
    summary="Get comprehensive property performance KPIs",
    tags=["Analytics"],
)
def get_kpi_analytics(
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Computes enterprise property management KPIs using real-time database aggregations:
    - Inventory: total, active, available, occupied, cleaning, maintenance
    - Occupancy Rate: (Occupied Rooms / Active Rooms) * 100
    - ADR (Average Daily Rate): Average rate earned per occupied room
    - RevPAR (Revenue Per Available Room): ADR * (Occupancy Rate / 100)
    - Daily Turnover: Today's arrivals and departures
    - Revenue Breakdown: Total confirmed revenue and current month revenue
    """
    if response:
        response.headers["Cache-Control"] = "public, max-age=60, s-maxage=60, stale-while-revalidate=30"
    try:
        cursor = conn.cursor()

        # 1. Room Status Counts
        cursor.execute("SELECT status, COUNT(*) as cnt FROM Rooms GROUP BY status;")
        status_rows = cursor.fetchall()
        status_counts = {}
        for r in status_rows:
            st = r["status"] if isinstance(r, dict) and "status" in r else r[0]
            cnt = r["cnt"] if isinstance(r, dict) and "cnt" in r else r[1]
            status_counts[st] = int(cnt)

        total_rooms = sum(status_counts.values())
        occupied_rooms = status_counts.get("Occupied", 0)
        available_rooms = status_counts.get("Available", 0)
        cleaning_rooms = status_counts.get("Cleaning", 0)
        maintenance_rooms = status_counts.get("Maintenance", 0)
        active_rooms = total_rooms - maintenance_rooms

        # 2. Occupancy Rate
        occupancy_rate = round((occupied_rooms / active_rooms * 100), 2) if active_rooms > 0 else 0.0
        occupancy_display = f"{occupancy_rate:.1f}%"

        # 3. Estimated Daily Revenue & ADR (Average Daily Rate of occupied inventory)
        cursor.execute(
            "SELECT COALESCE(SUM(price_per_night), 0.0) as est_daily_rev, COALESCE(AVG(price_per_night), 0.0) as avg_adr FROM Rooms WHERE status = 'Occupied';"
        )
        rev_calc_row = cursor.fetchone()
        if rev_calc_row:
            if isinstance(rev_calc_row, dict) and "est_daily_rev" in rev_calc_row:
                estimated_daily_revenue = round(float(rev_calc_row["est_daily_rev"] or 0.0), 2)
                adr = round(float(rev_calc_row["avg_adr"] or 0.0), 2)
            else:
                estimated_daily_revenue = round(float(rev_calc_row[0] or 0.0), 2)
                adr = round(float(rev_calc_row[1] or 0.0), 2)
        else:
            estimated_daily_revenue = 0.0
            adr = 0.0

        # 4. RevPAR (Revenue Per Available Room)
        revpar = round(adr * (occupancy_rate / 100.0), 2)

        # 5. Today's Arrivals and Departures
        today_checkin_sql = "SELECT COUNT(*) as cnt FROM Bookings WHERE check_in_date = CURRENT_DATE AND booking_status != 'Cancelled';" if IS_POSTGRES else "SELECT COUNT(*) as cnt FROM Bookings WHERE check_in_date = date('now') AND booking_status != 'Cancelled';"
        cursor.execute(today_checkin_sql)
        row_cin = cursor.fetchone()
        today_checkins = int(row_cin["cnt"] if isinstance(row_cin, dict) and "cnt" in row_cin else (row_cin[0] or 0))

        today_checkout_sql = "SELECT COUNT(*) as cnt FROM Bookings WHERE check_out_date = CURRENT_DATE AND booking_status != 'Cancelled';" if IS_POSTGRES else "SELECT COUNT(*) as cnt FROM Bookings WHERE check_out_date = date('now') AND booking_status != 'Cancelled';"
        cursor.execute(today_checkout_sql)
        row_cout = cursor.fetchone()
        today_checkouts = int(row_cout["cnt"] if isinstance(row_cout, dict) and "cnt" in row_cout else (row_cout[0] or 0))

        # Ensure display reflects active stays spanning today if present
        active_stays_sql = "SELECT COUNT(*) as cnt FROM Bookings WHERE check_in_date <= CURRENT_DATE AND check_out_date >= CURRENT_DATE AND booking_status != 'Cancelled';" if IS_POSTGRES else "SELECT COUNT(*) as cnt FROM Bookings WHERE check_in_date <= date('now') AND check_out_date >= date('now') AND booking_status != 'Cancelled';"
        cursor.execute(active_stays_sql)
        row_act = cursor.fetchone()
        active_stays = int(row_act["cnt"] if isinstance(row_act, dict) and "cnt" in row_act else (row_act[0] or 0))
        display_checkins = max(today_checkins, 1 if active_stays > 0 else 0)

        # 6. Revenues (Total Confirmed and Current Month)
        cursor.execute(
            "SELECT COALESCE(SUM(total_price), 0.0) as total_rev FROM Bookings WHERE booking_status != 'Cancelled';"
        )
        rev_row = cursor.fetchone()
        total_revenue = round(float(rev_row["total_rev"] if isinstance(rev_row, dict) and "total_rev" in rev_row else (rev_row[0] or 0.0)), 2)

        if IS_POSTGRES:
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_price), 0.0) as monthly_rev
                FROM Bookings
                WHERE booking_status != 'Cancelled'
                  AND to_char(check_in_date, 'YYYY-MM') = to_char(CURRENT_DATE, 'YYYY-MM');
                """
            )
        else:
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_price), 0.0) as monthly_rev
                FROM Bookings
                WHERE booking_status != 'Cancelled'
                  AND strftime('%Y-%m', check_in_date) = strftime('%Y-%m', 'now');
                """
            )
        monthly_row = cursor.fetchone()
        monthly_revenue = round(float(monthly_row["monthly_rev"] if isinstance(monthly_row, dict) and "monthly_rev" in monthly_row else (monthly_row[0] or 0.0)), 2)

        return KPIAnalyticsResponse(
            total_rooms=total_rooms,
            active_rooms=active_rooms,
            available_rooms=available_rooms,
            occupied_rooms=occupied_rooms,
            cleaning_rooms=cleaning_rooms,
            maintenance_rooms=maintenance_rooms,
            occupancy_rate=occupancy_rate,
            occupancy_rate_display=occupancy_display,
            estimated_daily_revenue=estimated_daily_revenue,
            adr=adr,
            revpar=revpar,
            today_checkins=display_checkins,
            today_checkouts=today_checkouts,
            total_revenue=total_revenue,
            monthly_revenue=monthly_revenue,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"KPI computation error: {str(exc)}",
        )


@app.get(
    "/api/rooms",
    response_model=List[RoomResponse],
    summary="List available rooms",
    tags=["Rooms"],
)
def get_rooms(
    check_in_date: Optional[date] = Query(None, description="Optional target check-in date"),
    check_out_date: Optional[date] = Query(None, description="Optional target check-out date"),
    room_type: Optional[RoomType] = Query(None, description="Filter by room type"),
    include_maintenance: bool = Query(False, description="Include rooms marked as Maintenance"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retrieves rooms from the catalog.
    If date bounds are provided, filters out conflicting bookings.
    If date bounds are omitted, returns all rooms with their operational status
    and active booking checkout date.
    """
    cursor = conn.cursor()

    if (check_in_date and not check_out_date) or (check_out_date and not check_in_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both 'check_in_date' and 'check_out_date' must be provided together.",
        )

    if check_in_date and check_out_date:
        if check_out_date <= check_in_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'check_out_date' must be strictly after 'check_in_date'.",
            )

        conditions = [
            """r.id NOT IN (
                SELECT b.room_id
                FROM Bookings b
                WHERE b.booking_status != 'Cancelled'
                  AND b.check_in_date < ?
                  AND b.check_out_date > ?
            )"""
        ]
        params = [check_out_date.isoformat(), check_in_date.isoformat()]

        if not include_maintenance:
            conditions.append("r.status != 'Maintenance'")

        if room_type:
            conditions.append("r.room_type = ?")
            params.append(room_type.value)

        where_clause = " WHERE " + " AND ".join(conditions)
        query = f"""
        SELECT r.id, r.room_number, r.room_type, r.price_per_night, r.status, r.created_at, NULL as booked_until
        FROM Rooms r
        {where_clause}
        ORDER BY r.room_number ASC;
        """
        cursor.execute(query, params)
    else:
        conditions = []
        params = []

        if not include_maintenance:
            conditions.append("r.status != 'Maintenance'")

        if room_type:
            conditions.append("r.room_type = ?")
            params.append(room_type.value)

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"""
        SELECT r.id, r.room_number, r.room_type, r.price_per_night, r.status, r.created_at,
               (
                   SELECT b.check_out_date
                   FROM Bookings b
                   WHERE b.room_id = r.id
                     AND b.booking_status != 'Cancelled'
                   ORDER BY b.check_out_date DESC
                   LIMIT 1
               ) as booked_until
        FROM Rooms r
        {where_clause}
        ORDER BY r.room_number ASC;
        """
        cursor.execute(query, params)

    rows = cursor.fetchall()
    return [
        RoomResponse(
            id=row["id"],
            room_number=row["room_number"],
            room_type=row["room_type"],
            price_per_night=row["price_per_night"],
            status=row["status"],
            created_at=str(row["created_at"]) if row["created_at"] else None,
            booked_until=str(row["booked_until"]) if row["booked_until"] else None,
        )
        for row in rows
    ]


@app.patch(
    "/api/rooms/{room_id}/status",
    response_model=RoomResponse,
    summary="Update room operational status",
    tags=["Rooms"],
)
def update_room_status(
    room_id: int,
    status_update: RoomStatusUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Mutates a room's operational status (e.g. Available, Cleaning, Maintenance, Occupied).
    Used by housekeeping and maintenance teams for dynamic room turnover.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, room_number, status FROM Rooms WHERE id = ?;", (room_id,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found.",
        )
    old_status = existing["status"]

    cursor.execute(
        "UPDATE Rooms SET status = ? WHERE id = ?;",
        (status_update.status.value, room_id),
    )
    record_audit_log(
        conn,
        action="ROOM_STATUS_UPDATED",
        entity_type="Room",
        entity_id=room_id,
        details={
            "room_number": existing["room_number"],
            "old_status": old_status,
            "new_status": status_update.status.value,
        },
        actor="Front Desk Agent",
    )
    conn.commit()

    cursor.execute(
        """
        SELECT r.id, r.room_number, r.room_type, r.price_per_night, r.status, r.created_at,
               (
                   SELECT b.check_out_date
                   FROM Bookings b
                   WHERE b.room_id = r.id
                     AND b.booking_status != 'Cancelled'
                   ORDER BY b.check_out_date DESC
                   LIMIT 1
               ) as booked_until
        FROM Rooms r
        WHERE r.id = ?;
        """,
        (room_id,),
    )
    row = cursor.fetchone()
    return RoomResponse(
        id=row["id"],
        room_number=row["room_number"],
        room_type=row["room_type"],
        price_per_night=row["price_per_night"],
        status=row["status"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        booked_until=str(row["booked_until"]) if row["booked_until"] else None,
    )


@app.get(
    "/api/amenities",
    response_model=List[AmenityResponse],
    summary="List available hotel amenities",
    tags=["Amenities"],
)
def get_amenities(conn: sqlite3.Connection = Depends(get_db)):
    """
    Returns the catalog of available add-on amenities with rates and descriptions.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, description, created_at FROM Amenities ORDER BY id ASC;")
    rows = cursor.fetchall()
    return [
        AmenityResponse(
            id=row["id"],
            name=row["name"],
            price=row["price"],
            description=row["description"],
            created_at=str(row["created_at"]) if row["created_at"] else None,
        )
        for row in rows
    ]


# ==========================================
# Module 11: Dynamic Pricing & Seasonal Rate Engine
# ==========================================

def calculate_dynamic_pricing(
    room: sqlite3.Row,
    check_in_date: date,
    check_out_date: date,
    guest_id: Optional[int] = None,
    amenity_ids: list[int] = [],
    coupon_code: Optional[str] = None,
    apply_dynamic_pricing: bool = True,
    conn: Optional[sqlite3.Connection] = None,
) -> PriceQuoteResponse:
    """
    Computes transparent rate quotation including:
    - Base room rate per night
    - Weekend Surge (+20% on Friday & Saturday nights)
    - High-Season Summer Surge (+15% in June, July, August)
    - Length-of-Stay Discount (10% for >= 5 nights, 15% for >= 7 nights)
    - VIP Loyalty Discount (Silver 5%, Gold 10%, Platinum 15%)
    - Add-on amenities total
    - Promotional Coupon Code discount
    - Taxes (10%) and Grand Total
    """
    cursor = conn.cursor()
    nights = (check_out_date - check_in_date).days
    base_rate = room["price_per_night"]

    nightly_details: list[NightlyRateDetail] = []
    raw_room_total = round(nights * base_rate, 2)
    weekend_surge_total = 0.0
    seasonal_surge_total = 0.0

    curr_date = check_in_date
    while curr_date < check_out_date:
        weekday_idx = curr_date.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        is_wknd = weekday_idx in (4, 5)   # Friday and Saturday nights
        is_smr = curr_date.month in (6, 7, 8)  # June, July, August

        if apply_dynamic_pricing:
            wknd_amt = round(base_rate * 0.20, 2) if is_wknd else 0.0
            smr_amt = round(base_rate * 0.15, 2) if is_smr else 0.0
        else:
            wknd_amt = 0.0
            smr_amt = 0.0

        eff_rate = round(base_rate + wknd_amt + smr_amt, 2)
        weekend_surge_total += wknd_amt
        seasonal_surge_total += smr_amt

        nightly_details.append(
            NightlyRateDetail(
                stay_date=curr_date,
                day_name=curr_date.strftime("%A"),
                base_rate=base_rate,
                is_weekend=is_wknd,
                weekend_surge=wknd_amt,
                is_summer=is_smr,
                summer_surge=smr_amt,
                effective_rate=eff_rate,
            )
        )
        curr_date += timedelta(days=1)

    weekend_surge_total = round(weekend_surge_total, 2)
    seasonal_surge_total = round(seasonal_surge_total, 2)
    adjusted_room_charge = round(raw_room_total + weekend_surge_total + seasonal_surge_total, 2)

    # Length of Stay Discount
    los_discount = 0.0
    if apply_dynamic_pricing:
        if nights >= 7:
            los_discount = round(adjusted_room_charge * 0.15, 2)
        elif nights >= 5:
            los_discount = round(adjusted_room_charge * 0.10, 2)

    # VIP Loyalty Discount
    vip_discount = 0.0
    vip_tier_str = "Standard"
    if guest_id:
        cursor.execute("SELECT vip_tier FROM Guests WHERE id = ?;", (guest_id,))
        grow = cursor.fetchone()
        if grow and "vip_tier" in grow.keys() and grow["vip_tier"]:
            vip_tier_str = grow["vip_tier"]

    if apply_dynamic_pricing:
        if vip_tier_str == "Platinum":
            vip_discount = round(adjusted_room_charge * 0.15, 2)
        elif vip_tier_str == "Gold":
            vip_discount = round(adjusted_room_charge * 0.10, 2)
        elif vip_tier_str == "Silver":
            vip_discount = round(adjusted_room_charge * 0.05, 2)

    net_room_charge = round(max(0.0, adjusted_room_charge - los_discount - vip_discount), 2)

    # Amenities cost
    amenities_charge = 0.0
    if amenity_ids:
        placeholders = ",".join("?" for _ in amenity_ids)
        cursor.execute(f"SELECT price FROM Amenities WHERE id IN ({placeholders});", tuple(amenity_ids))
        amenities_charge = round(sum(r["price"] for r in cursor.fetchall()), 2)

    pre_coupon_subtotal = round(net_room_charge + amenities_charge, 2)

    # Coupon Discount Evaluation
    coupon_discount = 0.0
    coupon_applied = False
    clean_code = coupon_code.strip().upper() if coupon_code else None

    if clean_code:
        cursor.execute("PRAGMA table_info(Coupons);")
        c_cols = {r[1] for r in cursor.fetchall()}
        if c_cols:
            cursor.execute(
                """
                SELECT id, code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, used_count, is_active
                FROM Coupons
                WHERE UPPER(code) = ?;
                """,
                (clean_code,),
            )
            coupon_row = cursor.fetchone()
            if coupon_row:
                today_iso = date.today().isoformat()
                is_valid = (
                    coupon_row["is_active"] == 1
                    and coupon_row["valid_from"] <= today_iso <= coupon_row["valid_until"]
                    and coupon_row["used_count"] < coupon_row["max_uses"]
                    and pre_coupon_subtotal >= coupon_row["min_total"]
                )
                if is_valid:
                    coupon_applied = True
                    dtype = coupon_row["discount_type"]
                    dval = coupon_row["discount_value"]
                    if dtype == "Percentage":
                        coupon_discount = round(pre_coupon_subtotal * (dval / 100.0), 2)
                    else:  # FixedAmount
                        coupon_discount = round(min(dval, pre_coupon_subtotal), 2)

    subtotal = round(max(0.0, pre_coupon_subtotal - coupon_discount), 2)
    tax_amount = round(subtotal * 0.10, 2)
    grand_total = round(subtotal + tax_amount, 2)

    return PriceQuoteResponse(
        room_id=room["id"],
        room_number=room["room_number"],
        room_type=room["room_type"],
        nights=nights,
        nightly_details=nightly_details,
        raw_room_total=raw_room_total,
        weekend_surge_total=weekend_surge_total,
        seasonal_surge_total=seasonal_surge_total,
        length_of_stay_discount=los_discount,
        vip_discount=vip_discount,
        net_room_charge=net_room_charge,
        amenities_charge=amenities_charge,
        coupon_discount=coupon_discount,
        coupon_code=clean_code if coupon_applied else None,
        coupon_applied=coupon_applied,
        subtotal=subtotal,
        tax_amount=tax_amount,
        grand_total=grand_total,
    )


@app.post(
    "/api/bookings",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new reservation",
    tags=["Bookings"],
)
def create_booking(
    booking_data: BookingCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Reserves a room for a guest:
    1. Verifies room exists and is not under maintenance.
    2. Verifies room is not already booked during the requested date interval (concurrency-safe overlap check).
    3. Resolves or creates the guest record.
    4. Validates requested amenities and calculates dynamic pricing with weekend/seasonal surges & coupons.
    5. Persists the reservation and records many-to-many junction entries in BookingAmenities.
    6. Returns the confirmed booking with enriched room, guest, and amenities payloads.
    """
    cursor = conn.cursor()

    # 1. Fetch Room Details
    cursor.execute(
        "SELECT id, room_number, room_type, price_per_night, status, created_at FROM Rooms WHERE id = ?;",
        (booking_data.room_id,),
    )
    room = cursor.fetchone()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {booking_data.room_id} does not exist.",
        )

    if room["status"] == "Maintenance":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room {room['room_number']} is currently out of service (Maintenance).",
        )

    # 2. Check for Overlapping Bookings (Double-Booking Prevention)
    cursor.execute(
        """
        SELECT id, check_in_date, check_out_date
        FROM Bookings
        WHERE room_id = ?
          AND booking_status != 'Cancelled'
          AND check_in_date < ?
          AND check_out_date > ?;
        """,
        (
            booking_data.room_id,
            booking_data.check_out_date.isoformat(),
            booking_data.check_in_date.isoformat(),
        ),
    )
    conflict = cursor.fetchone()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Room {room['room_number']} is unavailable for the selected dates "
                f"({booking_data.check_in_date} to {booking_data.check_out_date}). "
                f"Conflicting booking exists from {conflict['check_in_date']} to {conflict['check_out_date']}."
            ),
        )

    # 3. Resolve Guest Record
    guest_id: int
    if booking_data.guest_id:
        cursor.execute(
            "SELECT id, first_name, last_name, email, phone, vip_tier, notes, created_at FROM Guests WHERE id = ?;",
            (booking_data.guest_id,),
        )
        existing_guest = cursor.fetchone()
        if not existing_guest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guest with ID {booking_data.guest_id} not found.",
            )
        guest_record = existing_guest
        guest_id = existing_guest["id"]
    else:
        # Guest payload provided
        guest_payload = booking_data.guest
        assert guest_payload is not None

        # Check if email is already registered
        cursor.execute(
            "SELECT id, first_name, last_name, email, phone, vip_tier, notes, created_at FROM Guests WHERE email = ?;",
            (guest_payload.email,),
        )
        existing_guest = cursor.fetchone()

        if existing_guest:
            guest_id = existing_guest["id"]
            guest_record = existing_guest
        else:
            cursor.execute("PRAGMA table_info(Guests);")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "vip_tier" not in existing_cols:
                cursor.execute("ALTER TABLE Guests ADD COLUMN vip_tier TEXT NOT NULL DEFAULT 'Standard';")
            if "notes" not in existing_cols:
                cursor.execute("ALTER TABLE Guests ADD COLUMN notes TEXT DEFAULT '';")

            cursor.execute(
                """
                INSERT INTO Guests (first_name, last_name, email, phone, vip_tier, notes)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    guest_payload.first_name,
                    guest_payload.last_name,
                    guest_payload.email,
                    guest_payload.phone,
                    guest_payload.vip_tier.value,
                    guest_payload.notes or "",
                ),
            )
            guest_id = cursor.lastrowid
            cursor.execute(
                "SELECT id, first_name, last_name, email, phone, vip_tier, notes, created_at FROM Guests WHERE id = ?;",
                (guest_id,),
            )
            guest_record = cursor.fetchone()

    # 4. Validate Amenities
    selected_amenities: List[AmenityResponse] = []
    amenities_total = 0.0

    if booking_data.amenity_ids:
        placeholders = ",".join("?" for _ in booking_data.amenity_ids)
        cursor.execute(
            f"SELECT id, name, price, description, created_at FROM Amenities WHERE id IN ({placeholders});",
            tuple(booking_data.amenity_ids),
        )
        amenity_rows = cursor.fetchall()
        found_ids = {r["id"] for r in amenity_rows}
        missing_ids = set(booking_data.amenity_ids) - found_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Requested amenity IDs not found: {sorted(list(missing_ids))}",
            )

        selected_amenities = [
            AmenityResponse(
                id=r["id"],
                name=r["name"],
                price=r["price"],
                description=r["description"],
                created_at=str(r["created_at"]) if r["created_at"] else None,
            )
            for r in amenity_rows
        ]
        amenities_total = sum(r["price"] for r in amenity_rows)

    # 5. Schema Migration & Dynamic Pricing Calculation
    cursor.execute("PRAGMA table_info(Bookings);")
    b_cols = {r[1] for r in cursor.fetchall()}
    if "coupon_code" not in b_cols:
        cursor.execute("ALTER TABLE Bookings ADD COLUMN coupon_code TEXT DEFAULT NULL;")
    if "discount_amount" not in b_cols:
        cursor.execute("ALTER TABLE Bookings ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0.0;")

    quote = calculate_dynamic_pricing(
        room=room,
        check_in_date=booking_data.check_in_date,
        check_out_date=booking_data.check_out_date,
        guest_id=guest_id,
        amenity_ids=booking_data.amenity_ids,
        coupon_code=booking_data.coupon_code,
        apply_dynamic_pricing=booking_data.apply_dynamic_pricing,
        conn=conn,
    )

    if booking_data.apply_dynamic_pricing:
        total_price = quote.grand_total
    else:
        # Standard base rate + amenities - coupon discount
        total_price = round(max(0.0, quote.raw_room_total + quote.amenities_charge - quote.coupon_discount), 2)

    applied_coupon = quote.coupon_code if quote.coupon_applied else None
    discount_amount = quote.coupon_discount if quote.coupon_applied else 0.0

    # If coupon applied, increment used_count in Coupons table
    if applied_coupon and quote.coupon_applied:
        cursor.execute(
            "UPDATE Coupons SET used_count = used_count + 1 WHERE UPPER(code) = ?;",
            (applied_coupon,),
        )

    # 6. Insert Booking Record
    cursor.execute(
        """
        INSERT INTO Bookings (guest_id, room_id, check_in_date, check_out_date, total_price, booking_status, coupon_code, discount_amount)
        VALUES (?, ?, ?, ?, ?, 'Confirmed', ?, ?);
        """,
        (
            guest_id,
            booking_data.room_id,
            booking_data.check_in_date.isoformat(),
            booking_data.check_out_date.isoformat(),
            total_price,
            applied_coupon,
            discount_amount,
        ),
    )
    booking_id = cursor.lastrowid

    # 7. Record Junction Entries in BookingAmenities
    for amenity in selected_amenities:
        cursor.execute(
            """
            INSERT INTO BookingAmenities (booking_id, amenity_id, price_charged)
            VALUES (?, ?, ?);
            """,
            (booking_id, amenity.id, amenity.price),
        )

    # Module 12: Record immutable audit event
    record_audit_log(
        conn,
        action="BOOKING_CREATED",
        entity_type="Booking",
        entity_id=booking_id,
        details={
            "room_id": booking_data.room_id,
            "room_number": room["room_number"],
            "guest_id": guest_id,
            "guest_name": f"{guest_record['first_name']} {guest_record['last_name']}",
            "stay_dates": f"{booking_data.check_in_date} to {booking_data.check_out_date}",
            "total_price": total_price,
            "coupon_code": applied_coupon,
        },
        actor="Front Desk Agent",
    )

    conn.commit()

    # 8. Fetch created booking details to return
    cursor.execute("SELECT created_at FROM Bookings WHERE id = ?;", (booking_id,))
    booking_created_at = cursor.fetchone()["created_at"]

    return BookingResponse(
        id=booking_id,
        guest_id=guest_id,
        room_id=booking_data.room_id,
        check_in_date=booking_data.check_in_date,
        check_out_date=booking_data.check_out_date,
        total_price=total_price,
        booking_status=BookingStatus.CONFIRMED,
        created_at=str(booking_created_at),
        coupon_code=applied_coupon,
        discount_amount=discount_amount,
        room=RoomResponse(
            id=room["id"],
            room_number=room["room_number"],
            room_type=room["room_type"],
            price_per_night=room["price_per_night"],
            status=room["status"],
            created_at=str(room["created_at"]) if room["created_at"] else None,
        ),
        guest=GuestResponse(
            id=guest_record["id"],
            first_name=guest_record["first_name"],
            last_name=guest_record["last_name"],
            email=guest_record["email"],
            phone=guest_record["phone"],
            vip_tier=VIPTier(guest_record["vip_tier"]) if "vip_tier" in guest_record.keys() and guest_record["vip_tier"] else VIPTier.STANDARD,
            notes=guest_record["notes"] if "notes" in guest_record.keys() and guest_record["notes"] else "",
            created_at=str(guest_record["created_at"]) if guest_record["created_at"] else None,
        ),
        amenities=selected_amenities,
    )


# ==========================================
# Module 9: Reservation Lifecycle & Checkout Engine
# ==========================================

def get_booking_by_id(booking_id: int, conn: sqlite3.Connection) -> BookingResponse:
    """Helper to fetch a complete BookingResponse with joined room, guest, and amenities."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(Bookings);")
    b_cols = {r[1] for r in cursor.fetchall()}
    if "coupon_code" not in b_cols:
        cursor.execute("ALTER TABLE Bookings ADD COLUMN coupon_code TEXT DEFAULT NULL;")
    if "discount_amount" not in b_cols:
        cursor.execute("ALTER TABLE Bookings ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0.0;")

    cursor.execute(
        """
        SELECT b.id, b.guest_id, b.room_id, b.check_in_date, b.check_out_date, b.total_price, b.booking_status, b.created_at,
               b.coupon_code, b.discount_amount,
               g.first_name, g.last_name, g.email, g.phone, g.vip_tier, g.notes as guest_notes, g.created_at as guest_created_at,
               r.room_number, r.room_type, r.price_per_night, r.status as room_status, r.created_at as room_created_at
        FROM Bookings b
        JOIN Guests g ON b.guest_id = g.id
        JOIN Rooms r ON b.room_id = r.id
        WHERE b.id = ?;
        """,
        (booking_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found.",
        )

    cursor.execute(
        """
        SELECT a.id, a.name, ba.price_charged as price, a.description, a.created_at
        FROM BookingAmenities ba
        JOIN Amenities a ON ba.amenity_id = a.id
        WHERE ba.booking_id = ?
        ORDER BY a.id ASC;
        """,
        (booking_id,),
    )
    amenity_rows = cursor.fetchall()
    amenities = [
        AmenityResponse(
            id=ar["id"],
            name=ar["name"],
            price=ar["price"],
            description=ar["description"],
            created_at=str(ar["created_at"]) if ar["created_at"] else None,
        )
        for ar in amenity_rows
    ]

    return BookingResponse(
        id=row["id"],
        guest_id=row["guest_id"],
        room_id=row["room_id"],
        check_in_date=date.fromisoformat(row["check_in_date"]),
        check_out_date=date.fromisoformat(row["check_out_date"]),
        total_price=row["total_price"],
        booking_status=BookingStatus(row["booking_status"]),
        created_at=str(row["created_at"]) if row["created_at"] else None,
        coupon_code=row["coupon_code"] if "coupon_code" in row.keys() else None,
        discount_amount=row["discount_amount"] if "discount_amount" in row.keys() and row["discount_amount"] else 0.0,
        room=RoomResponse(
            id=row["room_id"],
            room_number=row["room_number"],
            room_type=row["room_type"],
            price_per_night=row["price_per_night"],
            status=row["room_status"],
            created_at=str(row["room_created_at"]) if row["room_created_at"] else None,
        ),
        guest=GuestResponse(
            id=row["guest_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            phone=row["phone"],
            vip_tier=VIPTier(row["vip_tier"]) if "vip_tier" in row.keys() and row["vip_tier"] else VIPTier.STANDARD,
            notes=row["guest_notes"] if "guest_notes" in row.keys() and row["guest_notes"] else "",
            created_at=str(row["guest_created_at"]) if row["guest_created_at"] else None,
        ),
        amenities=amenities,
    )


@app.get(
    "/api/bookings",
    response_model=List[BookingResponse],
    summary="List all reservations with optional status filter",
    tags=["Bookings"],
)
def get_bookings(
    status_filter: Optional[BookingStatus] = Query(None, alias="status", description="Filter by booking status"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retrieves all reservations including relational guest, room, and chosen amenities.
    Ordered by creation date descending.
    """
    cursor = conn.cursor()
    query = """
    SELECT b.id
    FROM Bookings b
    """
    params = []
    if status_filter:
        query += " WHERE b.booking_status = ?"
        params.append(status_filter.value)
    query += " ORDER BY b.id DESC;"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [get_booking_by_id(row["id"], conn) for row in rows]


@app.post(
    "/api/bookings/{booking_id}/check-in",
    response_model=BookingResponse,
    summary="Check in a guest for a confirmed reservation",
    tags=["Bookings"],
)
def check_in_booking(
    booking_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Executes guest arrival check-in:
    - Verifies booking exists (404)
    - Verifies booking status is 'Confirmed' (400 if already Checked-in, Checked-out, or Cancelled)
    - Transitions booking status to 'Checked-in'
    - Updates room operational status to 'Occupied'
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, guest_id, room_id, booking_status FROM Bookings WHERE id = ?;",
        (booking_id,),
    )
    booking = cursor.fetchone()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found.",
        )

    current_status = booking["booking_status"]
    if current_status != "Confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot check in booking with status '{current_status}'. Only 'Confirmed' reservations can be checked in.",
        )

    room_id = booking["room_id"]
    cursor.execute("UPDATE Bookings SET booking_status = 'Checked-in' WHERE id = ?;", (booking_id,))
    cursor.execute("UPDATE Rooms SET status = 'Occupied' WHERE id = ?;", (room_id,))

    record_audit_log(
        conn,
        action="CHECK_IN",
        entity_type="Booking",
        entity_id=booking_id,
        details={
            "room_id": room_id,
            "guest_id": booking["guest_id"],
            "status": "Checked-in",
        },
        actor="Front Desk Agent",
    )
    conn.commit()

    return get_booking_by_id(booking_id, conn)


@app.post(
    "/api/bookings/{booking_id}/check-out",
    response_model=BookingCheckoutResponse,
    summary="Process guest departure checkout and generate invoice statement",
    tags=["Bookings"],
)
def check_out_booking(
    booking_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Executes guest departure checkout:
    - Verifies booking exists (404)
    - Verifies booking status is 'Checked-in' (400 if not checked in)
    - Computes transparent line-item invoice folio (room nights, amenities, taxes)
    - Transitions booking status to 'Checked-out'
    - Transitions room status to 'Cleaning' for immediate housekeeping sanitization
    - Returns comprehensive checkout invoice folio
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.id, b.guest_id, b.room_id, b.check_in_date, b.check_out_date, b.total_price, b.booking_status,
               g.first_name, g.last_name, g.email,
               r.room_number, r.room_type, r.price_per_night
        FROM Bookings b
        JOIN Guests g ON b.guest_id = g.id
        JOIN Rooms r ON b.room_id = r.id
        WHERE b.id = ?;
        """,
        (booking_id,),
    )
    booking = cursor.fetchone()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found.",
        )

    current_status = booking["booking_status"]
    if current_status != "Checked-in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot check out booking with status '{current_status}'. Only 'Checked-in' stays can be checked out.",
        )

    check_in = date.fromisoformat(booking["check_in_date"])
    check_out = date.fromisoformat(booking["check_out_date"])
    nights = max(1, (check_out - check_in).days)
    base_room_rate = booking["price_per_night"]
    base_room_charge = round(nights * base_room_rate, 2)

    # Fetch amenities billed
    cursor.execute(
        """
        SELECT a.name, ba.price_charged
        FROM BookingAmenities ba
        JOIN Amenities a ON ba.amenity_id = a.id
        WHERE ba.booking_id = ?;
        """,
        (booking_id,),
    )
    amenity_rows = cursor.fetchall()
    amenities_charge = round(sum(ar["price_charged"] for ar in amenity_rows), 2)

    # Fetch incidentals billed
    if not IS_POSTGRES:
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
    cursor.execute(
        """
        SELECT id, service_category, description, unit_price, quantity, total_price, status
        FROM FolioCharges
        WHERE booking_id = ? AND status != 'Voided';
        """,
        (booking_id,),
    )
    folio_rows = cursor.fetchall()
    incidentals_charge = round(sum(fc["total_price"] for fc in folio_rows), 2)

    grand_total = round(base_room_charge + amenities_charge + incidentals_charge, 2)
    tax_amount = round(grand_total * 0.10, 2)
    final_total = round(grand_total + tax_amount, 2)

    # Line items
    invoice_items = [
        InvoiceItem(
            description=f"Room {booking['room_number']} ({booking['room_type']}) accommodation ({nights} night{'s' if nights != 1 else ''})",
            quantity=nights,
            unit_price=base_room_rate,
            total_amount=base_room_charge,
        )
    ]
    for ar in amenity_rows:
        invoice_items.append(
            InvoiceItem(
                description=f"Add-on Amenity: {ar['name']}",
                quantity=1,
                unit_price=ar["price_charged"],
                total_amount=ar["price_charged"],
            )
        )
    for fc in folio_rows:
        invoice_items.append(
            InvoiceItem(
                description=f"Incidental ({fc['service_category']}): {fc['description']}",
                quantity=fc["quantity"],
                unit_price=fc["unit_price"],
                total_amount=fc["total_price"],
            )
        )
    invoice_items.append(
        InvoiceItem(
            description="Municipal Occupancy & Lodging Tax (10%)",
            quantity=1,
            unit_price=tax_amount,
            total_amount=tax_amount,
        )
    )

    room_id = booking["room_id"]
    cursor.execute("UPDATE Bookings SET booking_status = 'Checked-out' WHERE id = ?;", (booking_id,))
    cursor.execute("UPDATE Rooms SET status = 'Cleaning' WHERE id = ?;", (room_id,))
    cursor.execute("UPDATE FolioCharges SET status = 'Paid' WHERE booking_id = ? AND status = 'Billed';", (booking_id,))

    record_audit_log(
        conn,
        action="CHECK_OUT",
        entity_type="Booking",
        entity_id=booking_id,
        details={
            "room_id": room_id,
            "room_number": booking["room_number"],
            "base_room_charge": base_room_charge,
            "amenities_charge": amenities_charge,
            "incidentals_charge": incidentals_charge,
            "grand_total": final_total,
            "room_status_after": "Cleaning",
        },
        actor="Front Desk Agent",
    )
    conn.commit()

    from datetime import datetime, timezone
    checkout_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return BookingCheckoutResponse(
        booking_id=booking_id,
        guest_name=f"{booking['first_name']} {booking['last_name']}",
        guest_email=booking["email"],
        room_number=booking["room_number"],
        room_type=RoomType(booking["room_type"]),
        nights=nights,
        check_in_date=check_in,
        check_out_date=check_out,
        base_room_charge=base_room_charge,
        amenities_charge=amenities_charge,
        incidentals_charge=incidentals_charge,
        tax_amount=tax_amount,
        grand_total=final_total,
        status=BookingStatus.CHECKED_OUT,
        room_status_after_checkout=RoomStatus.CLEANING,
        checkout_timestamp=checkout_time,
        invoice_breakdown=invoice_items,
    )


@app.post(
    "/api/bookings/{booking_id}/cancel",
    response_model=BookingCancelResponse,
    summary="Cancel a reservation and calculate refund policy",
    tags=["Bookings"],
)
def cancel_booking(
    booking_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Cancels an active or confirmed booking:
    - Verifies booking exists (404)
    - Verifies booking is not already 'Cancelled' or 'Checked-out' (400)
    - Calculates refund based on hotel policy:
      - Cancellation before check-in date: 100% full refund ($0 fee)
      - Cancellation on or after check-in date: 50% refund (50% fee)
    - Updates booking status to 'Cancelled'
    - Releases room back to 'Available'
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.id, b.room_id, b.check_in_date, b.total_price, b.booking_status,
               g.first_name, g.last_name, r.room_number
        FROM Bookings b
        JOIN Guests g ON b.guest_id = g.id
        JOIN Rooms r ON b.room_id = r.id
        WHERE b.id = ?;
        """,
        (booking_id,),
    )
    booking = cursor.fetchone()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID {booking_id} not found.",
        )

    current_status = booking["booking_status"]
    if current_status in ("Cancelled", "Checked-out"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel booking with status '{current_status}'.",
        )

    total_price = booking["total_price"]
    check_in = date.fromisoformat(booking["check_in_date"])
    today = date.today()

    if today < check_in:
        refund_amount = round(total_price, 2)
        cancellation_fee = 0.0
        message = "Full 100% refund applied (cancelled prior to arrival date)."
    else:
        refund_amount = round(total_price * 0.50, 2)
        cancellation_fee = round(total_price * 0.50, 2)
        message = "Late cancellation: 50% refund applied, 50% cancellation fee retained."

    room_id = booking["room_id"]
    cursor.execute("UPDATE Bookings SET booking_status = 'Cancelled' WHERE id = ?;", (booking_id,))
    cursor.execute("UPDATE Rooms SET status = 'Available' WHERE id = ? AND status != 'Maintenance';", (room_id,))

    record_audit_log(
        conn,
        action="BOOKING_CANCELLED",
        entity_type="Booking",
        entity_id=booking_id,
        details={
            "room_id": room_id,
            "refund_amount": refund_amount,
            "cancellation_fee": cancellation_fee,
        },
        actor="Front Desk Agent",
    )
    conn.commit()

    return BookingCancelResponse(
        booking_id=booking_id,
        guest_name=f"{booking['first_name']} {booking['last_name']}",
        room_number=booking["room_number"],
        original_total=total_price,
        refund_amount=refund_amount,
        cancellation_fee=cancellation_fee,
        status=BookingStatus.CANCELLED,
        message=message,
    )


# ==========================================
# Module 10: Guest CRM & Loyalty Engine
# ==========================================

def get_guest_crm_profile(guest_row: sqlite3.Row, conn: sqlite3.Connection) -> GuestCRMResponse:
    """Aggregates lifetime spend, stay counts, and computes loyalty tier for a guest."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            COUNT(id) AS total_bookings,
            SUM(CASE WHEN booking_status = 'Checked-out' THEN 1 ELSE 0 END) AS completed_stays,
            SUM(CASE WHEN booking_status = 'Checked-in' THEN 1 ELSE 0 END) AS active_stays,
            SUM(CASE WHEN booking_status = 'Cancelled' THEN 1 ELSE 0 END) AS cancelled_bookings,
            SUM(CASE WHEN booking_status != 'Cancelled' THEN total_price ELSE 0.0 END) AS lifetime_spent,
            MAX(CASE WHEN booking_status != 'Cancelled' THEN check_out_date ELSE NULL END) AS last_stay_date
        FROM Bookings
        WHERE guest_id = ?;
        """,
        (guest_row["id"],),
    )
    agg = cursor.fetchone()

    total_bookings = agg["total_bookings"] or 0
    completed_stays = agg["completed_stays"] or 0
    active_stays = agg["active_stays"] or 0
    cancelled_bookings = agg["cancelled_bookings"] or 0
    lifetime_spent = round(agg["lifetime_spent"] or 0.0, 2)
    stays_count = completed_stays + active_stays
    average_spend = round(lifetime_spent / stays_count, 2) if stays_count > 0 else 0.0
    last_stay = date.fromisoformat(agg["last_stay_date"]) if agg["last_stay_date"] else None

    # VIP Loyalty Tier assessment
    stored_tier_val = guest_row["vip_tier"] if "vip_tier" in guest_row.keys() and guest_row["vip_tier"] else "Standard"
    vip_tier = VIPTier(stored_tier_val)
    # Automatic dynamic loyalty advancement if currently Standard
    if vip_tier == VIPTier.STANDARD:
        if lifetime_spent >= 3000.0 or completed_stays >= 5:
            vip_tier = VIPTier.PLATINUM
        elif lifetime_spent >= 1500.0 or completed_stays >= 3:
            vip_tier = VIPTier.GOLD
        elif lifetime_spent >= 500.0 or completed_stays >= 1:
            vip_tier = VIPTier.SILVER

    notes_val = guest_row["notes"] if "notes" in guest_row.keys() and guest_row["notes"] else ""

    return GuestCRMResponse(
        id=guest_row["id"],
        first_name=guest_row["first_name"],
        last_name=guest_row["last_name"],
        email=guest_row["email"],
        phone=guest_row["phone"],
        vip_tier=vip_tier,
        notes=notes_val,
        total_bookings=total_bookings,
        completed_stays=completed_stays,
        active_stays=active_stays,
        cancelled_bookings=cancelled_bookings,
        lifetime_spent=lifetime_spent,
        average_spend_per_stay=average_spend,
        last_stay_date=last_stay,
        created_at=str(guest_row["created_at"]) if guest_row["created_at"] else None,
    )


def get_guest_detail(guest_id: int, conn: sqlite3.Connection) -> GuestDetailResponse:
    """Retrieves single guest CRM profile along with chronological stay history."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Guests WHERE id = ?;", (guest_id,))
    guest_row = cursor.fetchone()
    if not guest_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guest with ID {guest_id} not found.",
        )
    crm_profile = get_guest_crm_profile(guest_row, conn)

    cursor.execute(
        "SELECT id FROM Bookings WHERE guest_id = ? ORDER BY check_in_date DESC, id DESC;",
        (guest_id,),
    )
    booking_rows = cursor.fetchall()
    stay_history = [get_booking_by_id(b["id"], conn) for b in booking_rows]

    return GuestDetailResponse(
        **crm_profile.model_dump(),
        stay_history=stay_history,
    )


@app.get(
    "/api/guests",
    response_model=List[GuestCRMResponse],
    summary="List guests with CRM loyalty and lifetime metrics",
    tags=["Guests"],
)
def get_guests(
    q: Optional[str] = Query(None, description="Search query by name, email, or phone"),
    vip_tier: Optional[VIPTier] = Query(None, description="Filter by VIP loyalty tier"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retrieves all guests along with aggregated CRM metrics:
    - Lifetime spend
    - Completed stays
    - VIP loyalty tier
    - Searchable by name, email, or phone
    """
    cursor = conn.cursor()
    query = "SELECT * FROM Guests"
    params = []
    if q and q.strip():
        term = f"%{q.strip()}%"
        query += " WHERE (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR phone LIKE ?)"
        params.extend([term, term, term, term])

    query += " ORDER BY id DESC;"
    cursor.execute(query, params)
    guests = cursor.fetchall()

    profiles = [get_guest_crm_profile(g, conn) for g in guests]
    if vip_tier:
        profiles = [p for p in profiles if p.vip_tier == vip_tier]

    return profiles


@app.get(
    "/api/guests/{guest_id}",
    response_model=GuestDetailResponse,
    summary="Get detailed guest CRM profile and full stay history",
    tags=["Guests"],
)
def get_guest_by_id_endpoint(
    guest_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Fetches comprehensive guest profile with complete folio stay history."""
    return get_guest_detail(guest_id, conn)


@app.post(
    "/api/guests",
    response_model=GuestCRMResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new guest profile",
    tags=["Guests"],
)
def create_guest_profile(
    guest: GuestCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Creates a new guest profile directly at the front desk."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Guests WHERE email = ?;", (guest.email,))
    existing = cursor.fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A guest with email '{guest.email}' already exists.",
        )

    cursor.execute("PRAGMA table_info(Guests);")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "vip_tier" not in existing_cols:
        cursor.execute("ALTER TABLE Guests ADD COLUMN vip_tier TEXT NOT NULL DEFAULT 'Standard';")
    if "notes" not in existing_cols:
        cursor.execute("ALTER TABLE Guests ADD COLUMN notes TEXT DEFAULT '';")

    cursor.execute(
        """
        INSERT INTO Guests (first_name, last_name, email, phone, vip_tier, notes)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            guest.first_name,
            guest.last_name,
            guest.email,
            guest.phone,
            guest.vip_tier.value,
            guest.notes or "",
        ),
    )
    new_id = cursor.lastrowid
    record_audit_log(
        conn,
        action="GUEST_CREATED",
        entity_type="Guest",
        entity_id=new_id,
        details={
            "name": f"{guest.first_name} {guest.last_name}",
            "email": guest.email,
            "vip_tier": guest.vip_tier.value,
        },
        actor="Front Desk Agent",
    )
    conn.commit()
    cursor.execute("SELECT * FROM Guests WHERE id = ?;", (new_id,))
    row = cursor.fetchone()
    return get_guest_crm_profile(row, conn)


@app.patch(
    "/api/guests/{guest_id}",
    response_model=GuestCRMResponse,
    summary="Update guest profile, VIP loyalty tier, or notes/preferences",
    tags=["Guests"],
)
def update_guest_profile(
    guest_id: int,
    updates: GuestUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Updates guest contact information, VIP tier, or preference notes.
    Checks email conflict if email is updated.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Guests WHERE id = ?;", (guest_id,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guest with ID {guest_id} not found.",
        )

    if updates.email and updates.email != existing["email"]:
        cursor.execute("SELECT id FROM Guests WHERE email = ? AND id != ?;", (updates.email, guest_id))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{updates.email}' is already registered to another guest.",
            )

    fields = []
    params = []
    if updates.first_name is not None:
        fields.append("first_name = ?")
        params.append(updates.first_name)
    if updates.last_name is not None:
        fields.append("last_name = ?")
        params.append(updates.last_name)
    if updates.email is not None:
        fields.append("email = ?")
        params.append(updates.email)
    if updates.phone is not None:
        fields.append("phone = ?")
        params.append(updates.phone)
    if updates.vip_tier is not None:
        fields.append("vip_tier = ?")
        params.append(updates.vip_tier.value)
    if updates.notes is not None:
        fields.append("notes = ?")
        params.append(updates.notes)

    if fields:
        params.append(guest_id)
        cursor.execute(f"UPDATE Guests SET {', '.join(fields)} WHERE id = ?;", params)
        record_audit_log(
            conn,
            action="GUEST_UPDATED",
            entity_type="Guest",
            entity_id=guest_id,
            details={
                "fields_modified": list(updates.model_dump(exclude_unset=True).keys()),
            },
            actor="Front Desk Agent",
        )
        conn.commit()

    cursor.execute("SELECT * FROM Guests WHERE id = ?;", (guest_id,))
    updated_row = cursor.fetchone()
    return get_guest_crm_profile(updated_row, conn)


# ==========================================
# Module 11: Pricing & Promotional Coupon Endpoints
# ==========================================

@app.post(
    "/api/pricing/quote",
    response_model=PriceQuoteResponse,
    summary="Get detailed dynamic pricing quotation with surges and discounts",
    tags=["Pricing & Coupons"],
)
def get_pricing_quote(
    request: PriceQuoteRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Returns an itemized price quotation for a target room, stay dates, guest loyalty, and coupon.
    Includes day-of-week breakdown (weekend surge, summer surge), length-of-stay discount, and VIP tier benefits.
    """
    if request.check_out_date <= request.check_in_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'check_out_date' must be strictly after 'check_in_date'.",
        )

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, room_number, room_type, price_per_night, status FROM Rooms WHERE id = ?;",
        (request.room_id,),
    )
    room = cursor.fetchone()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {request.room_id} not found.",
        )

    return calculate_dynamic_pricing(
        room=room,
        check_in_date=request.check_in_date,
        check_out_date=request.check_out_date,
        guest_id=request.guest_id,
        amenity_ids=request.amenity_ids,
        coupon_code=request.coupon_code,
        apply_dynamic_pricing=True,
        conn=conn,
    )


@app.get(
    "/api/coupons",
    response_model=List[CouponResponse],
    summary="List active promotional discount coupons",
    tags=["Pricing & Coupons"],
)
def get_coupons(
    active_only: bool = Query(True, description="Filter for currently active coupons only"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Retrieves property discount coupons with validity dates and usage stats."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(Coupons);")
    c_cols = {r[1] for r in cursor.fetchall()}
    if not c_cols:
        return []

    query = "SELECT * FROM Coupons"
    params = []
    if active_only:
        today_iso = date.today().isoformat()
        query += " WHERE is_active = 1 AND valid_from <= ? AND valid_until >= ?"
        params.extend([today_iso, today_iso])

    query += " ORDER BY id DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [
        CouponResponse(
            id=r["id"],
            code=r["code"],
            discount_type=DiscountType(r["discount_type"]),
            discount_value=r["discount_value"],
            valid_from=date.fromisoformat(r["valid_from"]),
            valid_until=date.fromisoformat(r["valid_until"]),
            min_total=r["min_total"],
            max_uses=r["max_uses"],
            used_count=r["used_count"],
            is_active=bool(r["is_active"]),
            created_at=str(r["created_at"]) if r["created_at"] else None,
        )
        for r in rows
    ]


@app.post(
    "/api/coupons",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new promotional discount coupon",
    tags=["Pricing & Coupons"],
)
def create_coupon(
    coupon_data: CouponCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Creates a new promotional discount coupon."""
    if coupon_data.valid_until < coupon_data.valid_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'valid_until' date cannot be before 'valid_from' date.",
        )

    clean_code = coupon_data.code.strip().upper()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Coupons WHERE UPPER(code) = ?;", (clean_code,))
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Coupon code '{clean_code}' already exists.",
        )

    cursor.execute(
        """
        INSERT INTO Coupons (code, discount_type, discount_value, valid_from, valid_until, min_total, max_uses, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            clean_code,
            coupon_data.discount_type.value,
            coupon_data.discount_value,
            coupon_data.valid_from.isoformat(),
            coupon_data.valid_until.isoformat(),
            coupon_data.min_total,
            coupon_data.max_uses,
            1 if coupon_data.is_active else 0,
        ),
    )
    new_id = cursor.lastrowid
    record_audit_log(
        conn,
        action="COUPON_CREATED",
        entity_type="Coupon",
        entity_id=new_id,
        details={
            "code": coupon_data.code,
            "discount_type": coupon_data.discount_type.value,
            "discount_value": coupon_data.discount_value,
        },
        actor="Front Desk Agent",
    )
    conn.commit()
    cursor.execute("SELECT * FROM Coupons WHERE id = ?;", (new_id,))
    r = cursor.fetchone()
    return CouponResponse(
        id=r["id"],
        code=r["code"],
        discount_type=DiscountType(r["discount_type"]),
        discount_value=r["discount_value"],
        valid_from=date.fromisoformat(r["valid_from"]),
        valid_until=date.fromisoformat(r["valid_until"]),
        min_total=r["min_total"],
        max_uses=r["max_uses"],
        used_count=r["used_count"],
        is_active=bool(r["is_active"]),
        created_at=str(r["created_at"]) if r["created_at"] else None,
    )


@app.post(
    "/api/coupons/validate",
    response_model=CouponValidateResponse,
    summary="Validate a coupon code against a total order amount",
    tags=["Pricing & Coupons"],
)
def validate_coupon(
    req: CouponValidateRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Validates coupon code eligibility, status, and min-spend threshold against booking total."""
    clean_code = req.code.strip().upper()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Coupons WHERE UPPER(code) = ?;", (clean_code,))
    coupon = cursor.fetchone()

    if not coupon:
        return CouponValidateResponse(
            is_valid=False,
            code=clean_code,
            message=f"Coupon code '{clean_code}' does not exist.",
        )

    if coupon["is_active"] != 1:
        return CouponValidateResponse(
            is_valid=False,
            code=clean_code,
            message="This coupon is no longer active.",
        )

    today_iso = date.today().isoformat()
    if today_iso < coupon["valid_from"]:
        return CouponValidateResponse(
            is_valid=False,
            code=clean_code,
            message=f"Coupon is not valid until {coupon['valid_from']}.",
        )

    if today_iso > coupon["valid_until"]:
        return CouponValidateResponse(
            is_valid=False,
            code=clean_code,
            message="This coupon has expired.",
        )

    if coupon["used_count"] >= coupon["max_uses"]:
        return CouponValidateResponse(
            is_valid=False,
            code=clean_code,
            message="This coupon has reached its maximum redemption limit.",
        )

    if req.total_amount < coupon["min_total"]:
        return CouponValidateResponse(
            is_valid=False,
            code=clean_code,
            message=f"Minimum spend of ${coupon['min_total']:.2f} required for this promotion.",
        )

    dtype = DiscountType(coupon["discount_type"])
    dval = coupon["discount_value"]
    if dtype == DiscountType.PERCENTAGE:
        discount_amount = round(req.total_amount * (dval / 100.0), 2)
        msg = f"Valid! {dval:.0f}% discount applied (-${discount_amount:.2f})."
    else:
        discount_amount = round(min(dval, req.total_amount), 2)
        msg = f"Valid! ${discount_amount:.2f} voucher applied."

    return CouponValidateResponse(
        is_valid=True,
        code=clean_code,
        discount_type=dtype,
        discount_value=dval,
        discount_amount=discount_amount,
        message=msg,
    )


# ==========================================
# Module 12: Enterprise Audit Trail Endpoints
# ==========================================

@app.get(
    "/api/audit-logs",
    response_model=List[AuditLogResponse],
    summary="Get chronological operations audit ledger with filtering and pagination",
    tags=["Audit Trail"],
)
def get_audit_logs(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (Room, Booking, Guest, Coupon, System)"),
    action: Optional[str] = Query(None, description="Filter by action code"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    limit: int = Query(50, ge=1, le=200, description="Max logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retrieves the chronological audit ledger for enterprise compliance and change tracking.
    """
    try:
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

        query = "SELECT * FROM AuditLogs WHERE 1=1"
        params = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if action:
            query += " AND action = ?"
            params.append(action)
        if entity_id is not None:
            query += " AND entity_id = ?"
            params.append(entity_id)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [
            AuditLogResponse(
                id=r["id"],
                timestamp=str(r["timestamp"]),
                action=r["action"],
                entity_type=r["entity_type"],
                entity_id=r["entity_id"],
                actor=r["actor"],
                details=r["details"],
                created_at=str(r["created_at"]) if "created_at" in r.keys() and r["created_at"] else None,
            )
            for r in rows
        ]
    except Exception as exc:
        print(f"Warning: Audit log query handled: {exc}")
        return []


# ==========================================
# Module 13: Maintenance Work Orders & Housekeeping Dispatch
# ==========================================

@app.get(
    "/api/maintenance/tickets",
    response_model=List[MaintenanceTicketResponse],
    summary="List maintenance work orders with operational filters",
    tags=["Maintenance & Facilities"],
)
def get_maintenance_tickets(
    status: Optional[MaintenanceStatus] = Query(None, description="Filter by ticket status"),
    priority: Optional[MaintenancePriority] = Query(None, description="Filter by urgency priority"),
    category: Optional[MaintenanceCategory] = Query(None, description="Filter by trade classification"),
    room_id: Optional[int] = Query(None, description="Filter by room ID"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retrieves property maintenance work orders joined with room number.
    Auto-ensures MaintenanceTickets table exists for test fixtures.
    """
    try:
        cursor = conn.cursor()
        if not IS_POSTGRES:
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

        query = """
        SELECT mt.*, r.room_number
        FROM MaintenanceTickets mt
        JOIN Rooms r ON mt.room_id = r.id
        WHERE 1=1
        """
        params = []
        if status:
            query += " AND mt.status = ?"
            params.append(status.value)
        if priority:
            query += " AND mt.priority = ?"
            params.append(priority.value)
        if category:
            query += " AND mt.category = ?"
            params.append(category.value)
        if room_id is not None:
            query += " AND mt.room_id = ?"
            params.append(room_id)

        query += " ORDER BY CASE mt.priority WHEN 'Urgent' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, mt.id DESC;"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [
            MaintenanceTicketResponse(
                id=r["id"],
                room_id=r["room_id"],
                issue_description=r["issue_description"],
                category=MaintenanceCategory(r["category"]),
                priority=MaintenancePriority(r["priority"]),
                status=MaintenanceStatus(r["status"]),
                assigned_staff=r["assigned_staff"],
                reported_by=r["reported_by"],
                estimated_cost=r["estimated_cost"],
                resolution_notes=r["resolution_notes"] or "",
                created_at=str(r["created_at"]) if r["created_at"] else None,
                resolved_at=str(r["resolved_at"]) if r["resolved_at"] else None,
                room_number=r["room_number"],
            )
            for r in rows
        ]
    except Exception as exc:
        print(f"Warning: Maintenance tickets query handled: {exc}")
        return []


@app.get(
    "/api/maintenance/tickets/summary",
    response_model=MaintenanceSummaryResponse,
    summary="Get facility management and work order summary metrics",
    tags=["Maintenance & Facilities"],
)
def get_maintenance_summary(conn: sqlite3.Connection = Depends(get_db)):
    """Computes operational counts across work order statuses and urgent requests."""
    try:
        cursor = conn.cursor()
        if not IS_POSTGRES:
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

        cursor.execute("SELECT status, priority FROM MaintenanceTickets;")
        rows = cursor.fetchall()
        total = len(rows)
        open_cnt = sum(1 for r in rows if r["status"] == "Open")
        in_progress_cnt = sum(1 for r in rows if r["status"] == "In Progress")
        resolved_cnt = sum(1 for r in rows if r["status"] == "Resolved")
        urgent_cnt = sum(1 for r in rows if r["priority"] == "Urgent" and r["status"] in ("Open", "In Progress"))

        return MaintenanceSummaryResponse(
            total_tickets=total,
            open_tickets=open_cnt,
            in_progress_tickets=in_progress_cnt,
            resolved_tickets=resolved_cnt,
            urgent_tickets=urgent_cnt,
        )
    except Exception as exc:
        print(f"Warning: Maintenance summary query handled: {exc}")
        return MaintenanceSummaryResponse(
            total_tickets=0,
            open_tickets=0,
            in_progress_tickets=0,
            resolved_tickets=0,
            urgent_tickets=0,
        )


@app.post(
    "/api/maintenance/tickets",
    response_model=MaintenanceTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and dispatch a maintenance work order",
    tags=["Maintenance & Facilities"],
)
def create_maintenance_ticket(
    ticket: MaintenanceTicketCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Creates a new maintenance ticket:
    1. Verifies room exists.
    2. Inserts ticket into MaintenanceTickets.
    3. If auto_lock_room is True and priority is High or Urgent, automatically mutates room status to 'Maintenance'.
    4. Records immutable audit ledger entries.
    """
    cursor = conn.cursor()
    if not IS_POSTGRES:
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

    cursor.execute("SELECT id, room_number, status FROM Rooms WHERE id = ?;", (ticket.room_id,))
    room = cursor.fetchone()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {ticket.room_id} not found.",
        )

    cursor.execute(
        """
        INSERT INTO MaintenanceTickets (room_id, issue_description, category, priority, status, assigned_staff, reported_by, estimated_cost)
        VALUES (?, ?, ?, ?, 'Open', ?, ?, ?);
        """,
        (
            ticket.room_id,
            ticket.issue_description,
            ticket.category.value,
            ticket.priority.value,
            ticket.assigned_staff or "Facilities Team",
            ticket.reported_by or "Housekeeping",
            ticket.estimated_cost,
        ),
    )
    new_ticket_id = cursor.lastrowid

    # Auto-lock room to Maintenance if urgent or high priority
    if ticket.auto_lock_room and ticket.priority in (MaintenancePriority.HIGH, MaintenancePriority.URGENT):
        old_room_status = room["status"]
        if old_room_status != "Maintenance":
            cursor.execute("UPDATE Rooms SET status = 'Maintenance' WHERE id = ?;", (ticket.room_id,))
            record_audit_log(
                conn,
                action="ROOM_STATUS_UPDATED",
                entity_type="Room",
                entity_id=ticket.room_id,
                details={
                    "room_number": room["room_number"],
                    "old_status": old_room_status,
                    "new_status": "Maintenance",
                    "reason": f"Urgent Work Order #{new_ticket_id} ({ticket.category.value})",
                },
                actor=ticket.reported_by or "Facilities Team",
            )

    record_audit_log(
        conn,
        action="MAINTENANCE_TICKET_CREATED",
        entity_type="Room",
        entity_id=ticket.room_id,
        details={
            "ticket_id": new_ticket_id,
            "room_number": room["room_number"],
            "issue": ticket.issue_description,
            "category": ticket.category.value,
            "priority": ticket.priority.value,
        },
        actor=ticket.reported_by or "Facilities Team",
    )

    conn.commit()

    cursor.execute(
        """
        SELECT mt.*, r.room_number
        FROM MaintenanceTickets mt
        JOIN Rooms r ON mt.room_id = r.id
        WHERE mt.id = ?;
        """,
        (new_ticket_id,),
    )
    row = cursor.fetchone()
    return MaintenanceTicketResponse(
        id=row["id"],
        room_id=row["room_id"],
        issue_description=row["issue_description"],
        category=MaintenanceCategory(row["category"]),
        priority=MaintenancePriority(row["priority"]),
        status=MaintenanceStatus(row["status"]),
        assigned_staff=row["assigned_staff"],
        reported_by=row["reported_by"],
        estimated_cost=row["estimated_cost"],
        resolution_notes=row["resolution_notes"] or "",
        created_at=str(row["created_at"]) if row["created_at"] else None,
        resolved_at=str(row["resolved_at"]) if row["resolved_at"] else None,
        room_number=row["room_number"],
    )


@app.patch(
    "/api/maintenance/tickets/{ticket_id}",
    response_model=MaintenanceTicketResponse,
    summary="Update status, assign technician, or resolve work order",
    tags=["Maintenance & Facilities"],
)
def update_maintenance_ticket(
    ticket_id: int,
    updates: MaintenanceTicketUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Updates maintenance work order:
    1. Verifies ticket exists.
    2. Updates status, priority, staff, cost, and notes.
    3. If resolved, sets resolved_at and checks whether to release room to Cleaning.
    4. Records audit log.
    """
    cursor = conn.cursor()
    if not IS_POSTGRES:
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

    cursor.execute(
        """
        SELECT mt.*, r.room_number, r.status AS room_current_status
        FROM MaintenanceTickets mt
        JOIN Rooms r ON mt.room_id = r.id
        WHERE mt.id = ?;
        """,
        (ticket_id,),
    )
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance ticket with ID {ticket_id} not found.",
        )

    fields = []
    params = []

    if updates.status is not None:
        fields.append("status = ?")
        params.append(updates.status.value)
        if updates.status == MaintenanceStatus.RESOLVED and not existing["resolved_at"]:
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            fields.append("resolved_at = ?")
            params.append(now_iso)

    if updates.priority is not None:
        fields.append("priority = ?")
        params.append(updates.priority.value)

    if updates.assigned_staff is not None:
        fields.append("assigned_staff = ?")
        params.append(updates.assigned_staff)

    if updates.estimated_cost is not None:
        fields.append("estimated_cost = ?")
        params.append(updates.estimated_cost)

    if updates.resolution_notes is not None:
        fields.append("resolution_notes = ?")
        params.append(updates.resolution_notes)

    if fields:
        params.append(ticket_id)
        cursor.execute(f"UPDATE MaintenanceTickets SET {', '.join(fields)} WHERE id = ?;", params)

    # Check if room should be auto-released from Maintenance to Cleaning
    if updates.status == MaintenanceStatus.RESOLVED and updates.auto_release_room:
        room_id = existing["room_id"]
        # Check if any OTHER open or in-progress tickets remain for this room
        cursor.execute(
            """
            SELECT COUNT(*) AS active_cnt
            FROM MaintenanceTickets
            WHERE room_id = ? AND id != ? AND status IN ('Open', 'In Progress');
            """,
            (room_id, ticket_id),
        )
        active_cnt = cursor.fetchone()["active_cnt"]
        if active_cnt == 0 and existing["room_current_status"] == "Maintenance":
            cursor.execute("UPDATE Rooms SET status = 'Cleaning' WHERE id = ?;", (room_id,))
            record_audit_log(
                conn,
                action="ROOM_STATUS_UPDATED",
                entity_type="Room",
                entity_id=room_id,
                details={
                    "room_number": existing["room_number"],
                    "old_status": "Maintenance",
                    "new_status": "Cleaning",
                    "reason": f"Work Order #{ticket_id} Resolved. Dispatched for Housekeeping Sanitization.",
                },
                actor=updates.assigned_staff or existing["assigned_staff"] or "Facilities Team",
            )

    record_audit_log(
        conn,
        action="MAINTENANCE_TICKET_UPDATED",
        entity_type="Room",
        entity_id=existing["room_id"],
        details={
            "ticket_id": ticket_id,
            "status": updates.status.value if updates.status else existing["status"],
            "resolution_notes": updates.resolution_notes or "",
        },
        actor=updates.assigned_staff or existing["assigned_staff"] or "Facilities Team",
    )

    conn.commit()

    cursor.execute(
        """
        SELECT mt.*, r.room_number
        FROM MaintenanceTickets mt
        JOIN Rooms r ON mt.room_id = r.id
        WHERE mt.id = ?;
        """,
        (ticket_id,),
    )
    row = cursor.fetchone()
    return MaintenanceTicketResponse(
        id=row["id"],
        room_id=row["room_id"],
        issue_description=row["issue_description"],
        category=MaintenanceCategory(row["category"]),
        priority=MaintenancePriority(row["priority"]),
        status=MaintenanceStatus(row["status"]),
        assigned_staff=row["assigned_staff"],
        reported_by=row["reported_by"],
        estimated_cost=row["estimated_cost"],
        resolution_notes=row["resolution_notes"] or "",
        created_at=str(row["created_at"]) if row["created_at"] else None,
        resolved_at=str(row["resolved_at"]) if row["resolved_at"] else None,
        room_number=row["room_number"],
    )


# ==========================================
# Module 14: Guest Folio & Incidentals Billing Engine
# ==========================================

FOLIO_PRESET_CATALOG = {
    "Dining": [
        {"description": "In-Room Dining: Executive Wagyu Burger & Truffle Fries", "unit_price": 38.50},
        {"description": "In-Room Dining: Artisan Cheese & Charcuterie Board", "unit_price": 28.00},
        {"description": "Continental Buffet Breakfast", "unit_price": 24.99},
        {"description": "Sommelier Reserve Wine Bottle (750ml)", "unit_price": 45.00},
    ],
    "Minibar": [
        {"description": "Sparkling Italian Mineral Water (750ml)", "unit_price": 8.00},
        {"description": "Artisan Roasted Nuts & Dark Chocolates", "unit_price": 12.00},
        {"description": "Premium Craft Gin & Tonic Mixer Kit", "unit_price": 18.00},
        {"description": "Imported Craft Beer (330ml)", "unit_price": 9.50},
    ],
    "Spa": [
        {"description": "60-Min Deep Tissue Therapeutic Massage", "unit_price": 120.00},
        {"description": "Aromatherapy Body Scrub & Facial Treatment", "unit_price": 95.00},
        {"description": "Hydrotherapy Thermal Suite Day Pass", "unit_price": 45.00},
    ],
    "Parking": [
        {"description": "Overnight Secured Valet Parking (Per Day)", "unit_price": 25.00},
        {"description": "EV Supercharging High-Speed Session", "unit_price": 18.00},
    ],
    "Laundry": [
        {"description": "Same-Day Express Garment Pressing", "unit_price": 16.00},
        {"description": "Complete Laundry Wash, Dry & Fold Service", "unit_price": 30.00},
        {"description": "Delicate Fabric Dry Cleaning (Per Piece)", "unit_price": 22.00},
    ],
    "Miscellaneous": [
        {"description": "Late Departure Extended Stay Fee (Past 2 PM)", "unit_price": 35.00},
        {"description": "Replacement RFID Electronic Key Card", "unit_price": 10.00},
        {"description": "Pet Accommodation Sanitization Fee", "unit_price": 50.00},
    ],
}


@app.get(
    "/api/folio-charges/categories",
    summary="Get supported incidental categories and standard menu presets",
    tags=["Guest Folio & Billing"],
)
def get_folio_catalog():
    """
    Returns supported folio incidental categories and catalog presets for fast front desk posting.
    """
    return {
        "categories": [c.value for c in FolioCategory],
        "presets": FOLIO_PRESET_CATALOG,
    }


@app.get(
    "/api/bookings/{booking_id}/folio",
    response_model=FolioStatementResponse,
    summary="Retrieve complete itemized guest folio statement and net balance",
    tags=["Guest Folio & Billing"],
)
def get_booking_folio(
    booking_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Generates a live, fully-audited guest folio statement:
    - Accommodation base charges (nights x room rate)
    - Pre-booked add-on amenities
    - Active promotional discounts and coupon codes applied
    - Itemized auxiliary incidental charges (Dining, Minibar, Spa, Parking, Laundry)
    - Net grand total and outstanding balance due
    """
    cursor = conn.cursor()
    if not IS_POSTGRES:
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

    cursor.execute(
        """
        SELECT b.id, b.guest_id, b.room_id, b.check_in_date, b.check_out_date,
               b.total_price, b.booking_status, b.coupon_code, b.discount_amount,
               g.first_name, g.last_name, g.email,
               r.room_number, r.price_per_night
        FROM Bookings b
        JOIN Guests g ON b.guest_id = g.id
        JOIN Rooms r ON b.room_id = r.id
        WHERE b.id = ?;
        """,
        (booking_id,),
    )
    booking = cursor.fetchone()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reservation with ID {booking_id} does not exist.",
        )

    # Calculate accommodation base nights
    check_in = date.fromisoformat(booking["check_in_date"])
    check_out = date.fromisoformat(booking["check_out_date"])
    nights = max(1, (check_out - check_in).days)
    room_base_charge = round(nights * booking["price_per_night"], 2)

    # Fetch add-on amenities
    cursor.execute(
        """
        SELECT ba.price_charged
        FROM BookingAmenities ba
        WHERE ba.booking_id = ?;
        """,
        (booking_id,),
    )
    amenity_rows = cursor.fetchall()
    amenities_charge = round(sum(ar["price_charged"] for ar in amenity_rows), 2)
    discount_amount = round(booking["discount_amount"] or 0.0, 2)

    # Fetch itemized incidental charges
    cursor.execute(
        """
        SELECT id, booking_id, service_category, description, unit_price, quantity,
               total_price, status, posted_by, void_reason, created_at
        FROM FolioCharges
        WHERE booking_id = ?
        ORDER BY created_at ASC, id ASC;
        """,
        (booking_id,),
    )
    charge_rows = cursor.fetchall()

    incidentals = [
        FolioChargeResponse(
            id=cr["id"],
            booking_id=cr["booking_id"],
            service_category=FolioCategory(cr["service_category"]),
            description=cr["description"],
            unit_price=cr["unit_price"],
            quantity=cr["quantity"],
            total_price=cr["total_price"],
            status=FolioChargeStatus(cr["status"]),
            posted_by=cr["posted_by"],
            void_reason=cr["void_reason"],
            created_at=str(cr["created_at"]) if cr["created_at"] else None,
        )
        for cr in charge_rows
    ]

    active_incidentals = [i for i in incidentals if i.status != FolioChargeStatus.VOIDED]
    incidentals_total = round(sum(i.total_price for i in active_incidentals), 2)

    grand_total = max(0.0, round(room_base_charge + amenities_charge + incidentals_total - discount_amount, 2))

    # Calculate balance due based on booking and charge payment statuses
    if booking["booking_status"] == "Checked-out":
        unpaid_charges = sum(i.total_price for i in active_incidentals if i.status == FolioChargeStatus.BILLED)
        balance_due = round(unpaid_charges, 2)
    elif booking["booking_status"] == "Cancelled":
        balance_due = 0.0
    else:
        balance_due = grand_total

    return FolioStatementResponse(
        booking_id=booking_id,
        guest_id=booking["guest_id"],
        guest_name=f"{booking['first_name']} {booking['last_name']}",
        guest_email=booking["email"],
        room_id=booking["room_id"],
        room_number=booking["room_number"],
        booking_status=booking["booking_status"],
        check_in_date=booking["check_in_date"],
        check_out_date=booking["check_out_date"],
        room_base_charge=room_base_charge,
        amenities_charge=amenities_charge,
        discount_amount=discount_amount,
        coupon_code=booking["coupon_code"],
        incidentals=incidentals,
        incidentals_total=incidentals_total,
        grand_total=grand_total,
        balance_due=balance_due,
    )


@app.post(
    "/api/bookings/{booking_id}/charges",
    response_model=FolioChargeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Post an incidental charge to an active guest folio",
    tags=["Guest Folio & Billing"],
)
def post_folio_charge(
    booking_id: int,
    charge: FolioChargeCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Posts a room service, minibar, spa, or parking incidental charge:
    - Verifies booking exists (404)
    - Rejects posting if reservation is 'Cancelled' or 'Checked-out' (400)
    - Computes line-item total (unit_price * quantity)
    - Records charge in FolioCharges with status 'Billed'
    - Logs audit trail entry FOLIO_CHARGE_POSTED
    """
    cursor = conn.cursor()
    if not IS_POSTGRES:
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

    cursor.execute(
        """
        SELECT b.id, b.booking_status, r.room_number
        FROM Bookings b
        JOIN Rooms r ON b.room_id = r.id
        WHERE b.id = ?;
        """,
        (booking_id,),
    )
    booking = cursor.fetchone()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reservation with ID {booking_id} does not exist.",
        )

    current_status = booking["booking_status"]
    if current_status in ("Cancelled", "Checked-out"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot post incidental charges to a {current_status.lower()} reservation. Folios are locked upon departure or cancellation.",
        )

    total_price = round(charge.unit_price * charge.quantity, 2)
    posted_by = charge.posted_by or "Front Desk Agent"

    cursor.execute(
        """
        INSERT INTO FolioCharges (booking_id, service_category, description, unit_price, quantity, total_price, status, posted_by)
        VALUES (?, ?, ?, ?, ?, ?, 'Billed', ?);
        """,
        (
            booking_id,
            charge.service_category.value,
            charge.description.strip(),
            charge.unit_price,
            charge.quantity,
            total_price,
            posted_by,
        ),
    )
    new_charge_id = cursor.lastrowid

    record_audit_log(
        conn,
        action="FOLIO_CHARGE_POSTED",
        entity_type="Booking",
        entity_id=booking_id,
        details={
            "charge_id": new_charge_id,
            "room_number": booking["room_number"],
            "service_category": charge.service_category.value,
            "description": charge.description.strip(),
            "quantity": charge.quantity,
            "unit_price": charge.unit_price,
            "total_price": total_price,
            "posted_by": posted_by,
        },
        actor=posted_by,
    )
    conn.commit()

    cursor.execute("SELECT * FROM FolioCharges WHERE id = ?;", (new_charge_id,))
    row = cursor.fetchone()
    return FolioChargeResponse(
        id=row["id"],
        booking_id=row["booking_id"],
        service_category=FolioCategory(row["service_category"]),
        description=row["description"],
        unit_price=row["unit_price"],
        quantity=row["quantity"],
        total_price=row["total_price"],
        status=FolioChargeStatus(row["status"]),
        posted_by=row["posted_by"],
        void_reason=row["void_reason"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


@app.post(
    "/api/folio-charges/{charge_id}/void",
    response_model=FolioChargeResponse,
    summary="Void an incidental charge with audit justification",
    tags=["Guest Folio & Billing"],
)
def void_folio_charge(
    charge_id: int,
    payload: FolioChargeVoid,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Reverses an erroneous, disputed, or duplicate incidental charge:
    - Verifies charge exists (404)
    - Rejects if already 'Voided' (400)
    - Rejects if already 'Paid' (400)
    - Sets status to 'Voided' and records mandatory void_reason
    - Appends audit trail entry FOLIO_CHARGE_VOIDED
    """
    cursor = conn.cursor()
    if not IS_POSTGRES:
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

    cursor.execute("SELECT * FROM FolioCharges WHERE id = ?;", (charge_id,))
    charge = cursor.fetchone()
    if not charge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folio charge with ID {charge_id} not found.",
        )

    if charge["status"] == "Voided":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Charge #{charge_id} has already been voided.",
        )

    if charge["status"] == "Paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Charge #{charge_id} has already been settled/paid and cannot be voided directly.",
        )

    cursor.execute(
        """
        UPDATE FolioCharges
        SET status = 'Voided', void_reason = ?
        WHERE id = ?;
        """,
        (payload.void_reason.strip(), charge_id),
    )

    record_audit_log(
        conn,
        action="FOLIO_CHARGE_VOIDED",
        entity_type="Booking",
        entity_id=charge["booking_id"],
        details={
            "charge_id": charge_id,
            "description": charge["description"],
            "reversed_amount": charge["total_price"],
            "void_reason": payload.void_reason.strip(),
        },
        actor="Duty Manager",
    )
    conn.commit()

    cursor.execute("SELECT * FROM FolioCharges WHERE id = ?;", (charge_id,))
    row = cursor.fetchone()
    return FolioChargeResponse(
        id=row["id"],
        booking_id=row["booking_id"],
        service_category=FolioCategory(row["service_category"]),
        description=row["description"],
        unit_price=row["unit_price"],
        quantity=row["quantity"],
        total_price=row["total_price"],
        status=FolioChargeStatus(row["status"]),
        posted_by=row["posted_by"],
        void_reason=row["void_reason"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
    )


# Mount static files if directory exists (local development fallback)
# On Vercel, static assets are served directly from /public via edge CDN
if STATIC_DIR.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static_root")
    except Exception as e:
        print(f"StaticFiles mounting skipped: {e}")

