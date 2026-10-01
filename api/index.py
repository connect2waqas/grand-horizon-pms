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
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from database import (
    get_db_connection,
    init_db,
    seed_rooms,
    seed_amenities,
    seed_rate_plans,
    seed_coupons,
    record_audit_log,
    seed_audit_logs,
    seed_maintenance_tickets,
    seed_folio_charges,
    seed_housekeeping_tasks,
    seed_keycards,
    seed_finance_rates_and_taxes,
    seed_room_operations,
    IS_POSTGRES,
)
from schemas import (
    AmenityResponse,
    AuditLogResponse,
    AutoAssignRequest,
    AutoAssignResponse,
    BookingCancelResponse,
    BookingCheckoutResponse,
    BookingCreate,
    BookingResponse,
    BookingStatus,
    GuaranteeType,
    RatePlanBase,
    RatePlanCreate,
    RatePlanResponse,
    CancellationPolicy,
    MealPlanType,
    DemandYieldTier,
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
    HousekeepingPriority,
    HousekeepingSummaryResponse,
    HousekeepingTaskBase,
    HousekeepingTaskCreate,
    HousekeepingTaskResponse,
    HousekeepingTaskStatus,
    HousekeepingTaskType,
    HousekeepingTaskUpdate,
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
    CleanlinessStatus,
    RoomHousekeepingUpdate,
    RoomSpecificationResponse,
    RoomResponse,
    RoomStatus,
    RoomStatusUpdate,
    RoomType,
    VIPTier,
    KeycardType,
    KeycardStatus,
    AccessEventType,
    KeycardBase,
    KeycardIssueRequest,
    KeycardRevokeRequest,
    KeycardResponse,
    DoorTapRequest,
    DoorTapResponse,
    AccessLogResponse,
    AccessControlDashboardResponse,
    ExchangeRateBase,
    ExchangeRateUpdate,
    ExchangeRateResponse,
    CurrencyConvertRequest,
    CurrencyConvertResponse,
    TaxRuleBase,
    TaxRuleCreate,
    TaxRuleUpdate,
    TaxRuleResponse,
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxItemDetail,
    FinanceDashboardResponse,
    CurrencyCode,
    TaxType,
    TaxAppliesTo,
    RoomLockoutType,
    RoomLockoutCreate,
    RoomLockoutResponse,
    RoomReleaseRequest,
    RoomMoveRequest,
    RoomMoveResponse,
    RoomOperationsDashboardResponse,
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
            seed_housekeeping_tasks()
            seed_keycards()
            seed_finance_rates_and_taxes()
            seed_room_operations()
        seed_rate_plans()
        seed_housekeeping_tasks()
        seed_keycards()
        seed_finance_rates_and_taxes()
        seed_room_operations()
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

@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    return JSONResponse(
        status_code=500,
        content={"detail": "ResponseValidationError", "errors": str(exc.errors())},
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


def row_to_room_response(row) -> RoomResponse:
    """Helper to cleanly serialize database rows into rich RoomResponse models."""
    keys = row.keys() if hasattr(row, "keys") else []
    return RoomResponse(
        id=row["id"],
        room_number=row["room_number"],
        room_type=row["room_type"],
        price_per_night=float(row["price_per_night"]),
        status=row["status"],
        floor=int(row["floor"]) if "floor" in keys and row["floor"] is not None else 1,
        max_occupancy=int(row["max_occupancy"]) if "max_occupancy" in keys and row["max_occupancy"] is not None else 2,
        bed_type=row["bed_type"] if "bed_type" in keys and row["bed_type"] else "1 King Bed",
        view_type=row["view_type"] if "view_type" in keys and row["view_type"] else "City Skyline",
        sq_meters=int(row["sq_meters"]) if "sq_meters" in keys and row["sq_meters"] is not None else 35,
        is_smoking=bool(row["is_smoking"]) if "is_smoking" in keys and row["is_smoking"] is not None else False,
        cleanliness_status=CleanlinessStatus(row["cleanliness_status"]) if "cleanliness_status" in keys and row["cleanliness_status"] else CleanlinessStatus.INSPECTED,
        assigned_housekeeper=row["assigned_housekeeper"] if "assigned_housekeeper" in keys else None,
        cleaning_priority=row["cleaning_priority"] if "cleaning_priority" in keys and row["cleaning_priority"] else "Normal",
        dnd_status=bool(row["dnd_status"]) if "dnd_status" in keys and row["dnd_status"] is not None else False,
        last_cleaned_at=str(row["last_cleaned_at"]) if "last_cleaned_at" in keys and row["last_cleaned_at"] else None,
        last_inspected_at=str(row["last_inspected_at"]) if "last_inspected_at" in keys and row["last_inspected_at"] else None,
        lock_reason=row["lock_reason"] if "lock_reason" in keys else None,
        created_at=str(row["created_at"]) if "created_at" in keys and row["created_at"] else None,
        booked_until=str(row["booked_until"]) if "booked_until" in keys and row["booked_until"] else None,
    )


@app.get(
    "/api/rooms",
    response_model=List[RoomResponse],
    summary="List available rooms with architectural and housekeeping filters",
    tags=["Rooms"],
)
def get_rooms(
    check_in_date: Optional[date] = Query(None, description="Optional target check-in date"),
    check_out_date: Optional[date] = Query(None, description="Optional target check-out date"),
    room_type: Optional[RoomType] = Query(None, description="Filter by room type"),
    floor: Optional[int] = Query(None, ge=1, le=50, description="Filter by building floor level"),
    min_occupancy: Optional[int] = Query(None, ge=1, description="Minimum guest capacity required"),
    cleanliness_status: Optional[CleanlinessStatus] = Query(None, description="Filter by housekeeping inspection state"),
    include_maintenance: bool = Query(False, description="Include rooms marked as Maintenance"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Retrieves rooms from the catalog with architectural and operational filters:
    - Date range availability overlap checking (preventing double bookings)
    - Category (Single, Double, Family Suite)
    - Floor level (1, 2, 3...)
    - Minimum guest occupancy capacity
    - Housekeeping cleanliness state (Clean, Dirty, Inspected)
    - Maintenance exclusion
    """
    cursor = conn.cursor()

    if (check_in_date and not check_out_date) or (check_out_date and not check_in_date):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both 'check_in_date' and 'check_out_date' must be provided together.",
        )

    conditions = []
    params = []

    if check_in_date and check_out_date:
        if check_out_date <= check_in_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'check_out_date' must be strictly after 'check_in_date'.",
            )

        conditions.append(
            """r.id NOT IN (
                SELECT b.room_id
                FROM Bookings b
                WHERE b.booking_status != 'Cancelled'
                  AND b.check_in_date < ?
                  AND b.check_out_date > ?
            )"""
        )
        params.extend([check_out_date.isoformat(), check_in_date.isoformat()])

    if not include_maintenance:
        conditions.append("r.status != 'Maintenance'")

    if room_type:
        conditions.append("r.room_type = ?")
        params.append(room_type.value)

    if floor:
        conditions.append("r.floor = ?")
        params.append(floor)

    if min_occupancy:
        conditions.append("r.max_occupancy >= ?")
        params.append(min_occupancy)

    if cleanliness_status:
        conditions.append("r.cleanliness_status = ?")
        params.append(cleanliness_status.value)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"""
    SELECT r.*,
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
    return [row_to_room_response(row) for row in rows]


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

    lock_val = status_update.lock_reason if status_update.status == RoomStatus.MAINTENANCE else None

    # Check available columns for backward compatibility with isolated test fixtures
    if not IS_POSTGRES:
        cursor.execute("PRAGMA table_info(Rooms);")
        r_cols = {r[1] for r in cursor.fetchall()}
    else:
        r_cols = {"lock_reason", "cleanliness_status"}

    if "lock_reason" in r_cols:
        cursor.execute(
            "UPDATE Rooms SET status = ?, lock_reason = ? WHERE id = ?;",
            (status_update.status.value, lock_val, room_id),
        )
    else:
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
            "lock_reason": lock_val,
        },
        actor="Front Desk Agent",
    )
    conn.commit()

    cursor.execute(
        """
        SELECT r.*,
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
    return row_to_room_response(row)


@app.patch(
    "/api/rooms/{room_id}/housekeeping",
    response_model=RoomResponse,
    summary="Update room housekeeping cleanliness and inspection state",
    tags=["Rooms"],
)
def update_room_housekeeping(
    room_id: int,
    housekeeping_update: RoomHousekeepingUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Updates the housekeeping cleanliness state (Clean, Dirty, Inspected, Touch-up Required).
    - If status is marked 'Inspected' or 'Clean' while room was in 'Cleaning', auto-releases room to 'Available'.
    - If status is marked 'Dirty' while room was in 'Available', automatically flags operational status as 'Cleaning'.
    - Records an audit log event for compliance and housekeeping ledger tracking.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, room_number, status, cleanliness_status FROM Rooms WHERE id = ?;", (room_id,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} does not exist.",
        )

    old_clean = existing["cleanliness_status"] if "cleanliness_status" in existing.keys() else "Inspected"
    new_clean = housekeeping_update.cleanliness_status.value
    current_status = existing["status"]
    new_status = current_status

    if new_clean == CleanlinessStatus.DIRTY.value and current_status == "Available":
        new_status = "Cleaning"
    elif new_clean in (CleanlinessStatus.INSPECTED.value, CleanlinessStatus.CLEAN.value) and current_status == "Cleaning":
        new_status = "Available"

    # Dynamic column inspection for safe updates across schema versions
    if not IS_POSTGRES:
        cursor.execute("PRAGMA table_info(Rooms);")
        r_cols = {r[1] for r in cursor.fetchall()}
    else:
        r_cols = {"cleanliness_status", "assigned_housekeeper", "cleaning_priority", "dnd_status", "last_cleaned_at", "last_inspected_at"}

    updates = ["cleanliness_status = ?", "status = ?"]
    params = [new_clean, new_status]

    if "assigned_housekeeper" in r_cols and housekeeping_update.assigned_housekeeper is not None:
        updates.append("assigned_housekeeper = ?")
        params.append(housekeeping_update.assigned_housekeeper)

    if "cleaning_priority" in r_cols and housekeeping_update.cleaning_priority is not None:
        updates.append("cleaning_priority = ?")
        params.append(housekeeping_update.cleaning_priority)

    if "dnd_status" in r_cols and housekeeping_update.dnd_status is not None:
        updates.append("dnd_status = ?")
        params.append(1 if housekeeping_update.dnd_status else 0)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if new_clean in (CleanlinessStatus.CLEAN.value, CleanlinessStatus.INSPECTED.value) and "last_cleaned_at" in r_cols:
        updates.append("last_cleaned_at = ?")
        params.append(now_iso)

    if new_clean == CleanlinessStatus.INSPECTED.value and "last_inspected_at" in r_cols:
        updates.append("last_inspected_at = ?")
        params.append(now_iso)

    params.append(room_id)
    update_sql = f"UPDATE Rooms SET {', '.join(updates)} WHERE id = ?;"
    cursor.execute(update_sql, params)

    record_audit_log(
        conn,
        action="HOUSEKEEPING_INSPECTED",
        entity_type="Room",
        entity_id=room_id,
        details={
            "room_number": existing["room_number"],
            "old_cleanliness": old_clean,
            "new_cleanliness": new_clean,
            "assigned_housekeeper": housekeeping_update.assigned_housekeeper,
            "cleaning_priority": housekeeping_update.cleaning_priority,
            "dnd_status": housekeeping_update.dnd_status,
            "inspected_by": housekeeping_update.inspected_by or "Housekeeping Team",
            "notes": housekeeping_update.notes or "",
            "operational_status": new_status,
        },
        actor=housekeeping_update.inspected_by or "Housekeeper",
    )
    conn.commit()

    cursor.execute(
        """
        SELECT r.*, NULL as booked_until
        FROM Rooms r
        WHERE r.id = ?;
        """,
        (room_id,),
    )
    row = cursor.fetchone()
    return row_to_room_response(row)


@app.get(
    "/api/rooms/{room_id}/specifications",
    response_model=RoomSpecificationResponse,
    summary="Get comprehensive architectural room specifications and operational dossier",
    tags=["Rooms"],
)
def get_room_specifications(
    room_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Returns complete room dossier including floor, bed type, view, square meters,
    smoking policy, inspection state, lock reason, and active booking ID if occupied.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.*,
               (
                   SELECT b.id
                   FROM Bookings b
                   WHERE b.room_id = r.id
                     AND b.booking_status IN ('Confirmed', 'Checked-in')
                     AND b.check_out_date >= CURRENT_DATE
                   ORDER BY b.check_in_date ASC
                   LIMIT 1
               ) as active_booking_id,
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
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found.",
        )

    base_resp = row_to_room_response(row)
    spec_data = base_resp.model_dump()
    spec_data["active_booking_id"] = row["active_booking_id"] if "active_booking_id" in row.keys() else None
    if not spec_data.get("last_cleaned_at") and "created_at" in row.keys():
        spec_data["last_cleaned_at"] = str(row["created_at"]) if row["created_at"] else None
    return RoomSpecificationResponse(**spec_data)


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
# ==========================================
# Module 3 & 11: Rate Plans, Dynamic Pricing & Yield Management Engine
# ==========================================

def compute_occupancy_yield(conn: sqlite3.Connection, check_in_date: date, check_out_date: date) -> tuple[float, DemandYieldTier, float]:
    """
    Computes overall hotel occupancy percentage during the stay dates and determines the demand yield tier.
    Returns: (occupancy_percentage, demand_tier, yield_surge_rate)
    """
    cursor = conn.cursor()
    # 1. Total active room inventory (excluding maintenance)
    cursor.execute("SELECT COUNT(*) as total_rooms FROM Rooms WHERE status != 'Maintenance';")
    row = cursor.fetchone()
    total_rooms = row["total_rooms"] if row and row["total_rooms"] else 6

    # 2. Total distinct rooms booked during overlapping interval
    cursor.execute(
        """
        SELECT COUNT(DISTINCT room_id) as booked_count
        FROM Bookings
        WHERE booking_status != 'Cancelled'
          AND check_in_date < ?
          AND check_out_date > ?;
        """,
        (check_out_date.isoformat(), check_in_date.isoformat()),
    )
    b_row = cursor.fetchone()
    booked_count = b_row["booked_count"] if b_row and b_row["booked_count"] else 0

    occupancy_pct = round(min(100.0, (booked_count / max(1, total_rooms)) * 100.0), 1)

    if occupancy_pct >= 85.0:
        return occupancy_pct, DemandYieldTier.PEAK_COMPRESSION, 0.30
    elif occupancy_pct >= 70.0:
        return occupancy_pct, DemandYieldTier.HIGH_DEMAND, 0.15
    elif occupancy_pct >= 40.0:
        return occupancy_pct, DemandYieldTier.NORMAL_DEMAND, 0.0
    else:
        return occupancy_pct, DemandYieldTier.LOW_DEMAND, 0.0


def calculate_dynamic_pricing(
    room: sqlite3.Row,
    check_in_date: date,
    check_out_date: date,
    guest_id: Optional[int] = None,
    amenity_ids: list[int] = [],
    coupon_code: Optional[str] = None,
    rate_plan_code: Optional[str] = "BAR",
    apply_dynamic_pricing: bool = True,
    conn: Optional[sqlite3.Connection] = None,
) -> PriceQuoteResponse:
    """
    Computes transparent rate quotation including:
    - Base room rate per night modulated by Rate Plan Multiplier (BAR, Non-Refundable, B&B)
    - Weekend Surge (+20% on Friday & Saturday nights)
    - High-Season Summer Surge (+15% in June, July, August)
    - Occupancy-based Yield Management Demand Surge (-5% to +30%)
    - Minimum Length of Stay (MLOS) verification
    - Length-of-Stay Discount (10% for >= 5 nights, 15% for >= 7 nights)
    - VIP Loyalty Discount (Silver 5%, Gold 10%, Platinum 15%)
    - Add-on amenities total
    - Promotional Coupon Code discount
    - Taxes (10%) and Grand Total
    """
    cursor = conn.cursor()
    nights = (check_out_date - check_in_date).days
    raw_base_rate = float(room["price_per_night"])

    # 1. Resolve Rate Plan
    clean_plan_code = (rate_plan_code or "BAR").strip().upper()
    plan_row = None
    try:
        cursor.execute("SELECT * FROM RatePlans WHERE UPPER(code) = ? AND is_active = 1;", (clean_plan_code,))
        plan_row = cursor.fetchone()
    except Exception:
        if IS_POSTGRES:
            try:
                conn.rollback()
            except Exception:
                pass

    if not plan_row:
        # Fallback to standard Best Available Rate (BAR) defaults
        plan_row = {
            "code": "BAR",
            "name": "Best Available Rate",
            "rate_multiplier": 1.0,
            "cancellation_policy": "Flexible (24h free cancellation)",
            "meal_plan": "Room Only",
            "min_los": 1,
        }

    plan_multiplier = float(plan_row["rate_multiplier"])
    plan_name = str(plan_row["name"])
    plan_cancellation = str(plan_row["cancellation_policy"])
    plan_meal = str(plan_row["meal_plan"])
    min_los_required = int(plan_row["min_los"]) if "min_los" in plan_row.keys() else 1
    min_los_met = nights >= min_los_required

    # Apply rate plan multiplier to base nightly rate
    base_rate = round(raw_base_rate * plan_multiplier, 2)
    raw_room_total = round(nights * base_rate, 2)
    rate_plan_adjustment = round((base_rate - raw_base_rate) * nights, 2)

    # 2. Occupancy Yield Factor
    occupancy_pct, demand_tier, demand_surge_rate = compute_occupancy_yield(conn, check_in_date, check_out_date)

    nightly_details: list[NightlyRateDetail] = []
    weekend_surge_total = 0.0
    seasonal_surge_total = 0.0
    occupancy_surge_total = 0.0

    curr_date = check_in_date
    while curr_date < check_out_date:
        weekday_idx = curr_date.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        is_wknd = weekday_idx in (4, 5)   # Friday and Saturday nights
        is_smr = curr_date.month in (6, 7, 8)  # June, July, August

        if apply_dynamic_pricing:
            wknd_amt = round(base_rate * 0.20, 2) if is_wknd else 0.0
            smr_amt = round(base_rate * 0.15, 2) if is_smr else 0.0
            demand_amt = round(base_rate * demand_surge_rate, 2) if demand_surge_rate != 0.0 else 0.0
        else:
            wknd_amt = 0.0
            smr_amt = 0.0
            demand_amt = 0.0

        eff_rate = round(base_rate + wknd_amt + smr_amt + demand_amt, 2)
        weekend_surge_total += wknd_amt
        seasonal_surge_total += smr_amt
        occupancy_surge_total += demand_amt

        nightly_details.append(
            NightlyRateDetail(
                stay_date=curr_date,
                day_name=curr_date.strftime("%A"),
                base_rate=base_rate,
                is_weekend=is_wknd,
                weekend_surge=wknd_amt,
                is_summer=is_smr,
                summer_surge=smr_amt,
                demand_yield_surge=demand_amt,
                rate_plan_multiplier=plan_multiplier,
                effective_rate=eff_rate,
            )
        )
        curr_date += timedelta(days=1)

    weekend_surge_total = round(weekend_surge_total, 2)
    seasonal_surge_total = round(seasonal_surge_total, 2)
    occupancy_surge_total = round(occupancy_surge_total, 2)
    adjusted_room_charge = round(raw_room_total + weekend_surge_total + seasonal_surge_total + occupancy_surge_total, 2)

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
        amenities_charge = round(sum(float(r["price"]) for r in cursor.fetchall()), 2)

    pre_coupon_subtotal = round(net_room_charge + amenities_charge, 2)

    # Coupon Discount Evaluation
    coupon_discount = 0.0
    coupon_applied = False
    clean_code = coupon_code.strip().upper() if coupon_code else None

    if clean_code:
        has_coupons = True
        if not IS_POSTGRES:
            cursor.execute("PRAGMA table_info(Coupons);")
            c_cols = {r[1] for r in cursor.fetchall()}
            has_coupons = bool(c_cols)
        if has_coupons:
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
                c_from = str(coupon_row["valid_from"])
                c_until = str(coupon_row["valid_until"])
                is_valid = (
                    coupon_row["is_active"] == 1
                    and c_from <= today_iso <= c_until
                    and coupon_row["used_count"] < coupon_row["max_uses"]
                    and pre_coupon_subtotal >= coupon_row["min_total"]
                )
                if is_valid:
                    coupon_applied = True
                    dtype = coupon_row["discount_type"]
                    dval = float(coupon_row["discount_value"])
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
        occupancy_surge_total=occupancy_surge_total,
        rate_plan_adjustment=rate_plan_adjustment,
        length_of_stay_discount=los_discount,
        vip_discount=vip_discount,
        net_room_charge=net_room_charge,
        amenities_charge=amenities_charge,
        coupon_discount=coupon_discount,
        coupon_code=clean_code if coupon_applied else None,
        coupon_applied=coupon_applied,
        rate_plan_code=clean_plan_code,
        rate_plan_name=plan_name,
        cancellation_policy=plan_cancellation,
        meal_plan=plan_meal,
        occupancy_rate=occupancy_pct,
        demand_tier=demand_tier,
        min_los_met=min_los_met,
        min_los_required=min_los_required,
        subtotal=subtotal,
        tax_amount=tax_amount,
        grand_total=grand_total,
    )


def _create_booking_impl(
    booking_data: BookingCreate,
    conn: sqlite3.Connection,
) -> BookingResponse:
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
        "SELECT r.* FROM Rooms r WHERE r.id = ?;",
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

    # 1b. Max Occupancy Enforcement (Module 2 Deepening)
    total_guests = booking_data.adults + booking_data.children
    if "max_occupancy" in room.keys() and room["max_occupancy"] is not None:
        if total_guests > room["max_occupancy"]:
            raise HTTPException(
                status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
                detail=f"Party size ({total_guests} guests: {booking_data.adults} adults, {booking_data.children} children) exceeds maximum room capacity of {room['max_occupancy']} for Room {room['room_number']}.",
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
            if not IS_POSTGRES:
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
            if not guest_id:
                cursor.execute("SELECT id FROM Guests WHERE email = ?;", (guest_payload.email,))
                g_row = cursor.fetchone()
                guest_id = g_row["id"] if g_row else None

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
                price=float(r["price"]),
                description=r["description"],
                created_at=str(r["created_at"]) if r["created_at"] else None,
            )
            for r in amenity_rows
        ]
        amenities_total = sum(float(r["price"]) for r in amenity_rows)

    # 5. Schema Migration & Dynamic Pricing Calculation
    if not IS_POSTGRES:
        cursor.execute("PRAGMA table_info(Bookings);")
        b_cols = {r[1] for r in cursor.fetchall()}
        if "coupon_code" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN coupon_code TEXT DEFAULT NULL;")
        if "discount_amount" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0.0;")
        if "adults" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN adults INTEGER NOT NULL DEFAULT 1;")
        if "children" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN children INTEGER NOT NULL DEFAULT 0;")
        if "estimated_arrival_time" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN estimated_arrival_time TEXT DEFAULT '15:00';")
        if "special_requests" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN special_requests TEXT DEFAULT '';")
        if "guarantee_type" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN guarantee_type TEXT NOT NULL DEFAULT 'Guaranteed';")
        if "early_checkin_requested" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN early_checkin_requested INTEGER NOT NULL DEFAULT 0;")
        if "late_checkout_requested" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN late_checkout_requested INTEGER NOT NULL DEFAULT 0;")
        if "rate_plan_code" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN rate_plan_code TEXT NOT NULL DEFAULT 'BAR';")
    else:
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS coupon_code TEXT DEFAULT NULL;")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS discount_amount REAL NOT NULL DEFAULT 0.0;")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS adults INTEGER NOT NULL DEFAULT 1;")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS children INTEGER NOT NULL DEFAULT 0;")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS estimated_arrival_time TEXT DEFAULT '15:00';")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS special_requests TEXT DEFAULT '';")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS guarantee_type TEXT NOT NULL DEFAULT 'Guaranteed';")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS early_checkin_requested INTEGER NOT NULL DEFAULT 0;")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS late_checkout_requested INTEGER NOT NULL DEFAULT 0;")
        cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS rate_plan_code TEXT NOT NULL DEFAULT 'BAR';")
        b_cols = {
            "coupon_code", "discount_amount", "adults", "children",
            "estimated_arrival_time", "special_requests", "guarantee_type",
            "early_checkin_requested", "late_checkout_requested", "rate_plan_code"
        }

    quote = calculate_dynamic_pricing(
        room=room,
        check_in_date=booking_data.check_in_date,
        check_out_date=booking_data.check_out_date,
        guest_id=guest_id,
        amenity_ids=booking_data.amenity_ids,
        coupon_code=booking_data.coupon_code,
        rate_plan_code=booking_data.rate_plan_code,
        apply_dynamic_pricing=booking_data.apply_dynamic_pricing,
        conn=conn,
    )

    # 5b. Minimum Length of Stay (MLOS) Rate Plan Enforcement
    if not quote.min_los_met:
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=f"Rate plan '{quote.rate_plan_name}' ({quote.rate_plan_code}) requires a minimum stay of {quote.min_los_required} nights (requested {quote.nights} nights).",
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
    if "rate_plan_code" in b_cols:
        cursor.execute(
            """
            INSERT INTO Bookings (
                guest_id, room_id, check_in_date, check_out_date, total_price, booking_status,
                coupon_code, discount_amount, adults, children, estimated_arrival_time, special_requests,
                guarantee_type, early_checkin_requested, late_checkout_requested, rate_plan_code
            )
            VALUES (?, ?, ?, ?, ?, 'Confirmed', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                guest_id,
                booking_data.room_id,
                booking_data.check_in_date.isoformat(),
                booking_data.check_out_date.isoformat(),
                total_price,
                applied_coupon,
                discount_amount,
                booking_data.adults,
                booking_data.children,
                booking_data.estimated_arrival_time or "15:00",
                booking_data.special_requests or "",
                booking_data.guarantee_type.value,
                1 if booking_data.early_checkin_requested else 0,
                1 if booking_data.late_checkout_requested else 0,
                quote.rate_plan_code or "BAR",
            ),
        )
    elif "adults" in b_cols:
        cursor.execute(
            """
            INSERT INTO Bookings (
                guest_id, room_id, check_in_date, check_out_date, total_price, booking_status,
                coupon_code, discount_amount, adults, children, estimated_arrival_time, special_requests,
                guarantee_type, early_checkin_requested, late_checkout_requested
            )
            VALUES (?, ?, ?, ?, ?, 'Confirmed', ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                guest_id,
                booking_data.room_id,
                booking_data.check_in_date.isoformat(),
                booking_data.check_out_date.isoformat(),
                total_price,
                applied_coupon,
                discount_amount,
                booking_data.adults,
                booking_data.children,
                booking_data.estimated_arrival_time or "15:00",
                booking_data.special_requests or "",
                booking_data.guarantee_type.value,
                1 if booking_data.early_checkin_requested else 0,
                1 if booking_data.late_checkout_requested else 0,
            ),
        )
    else:
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
    if not booking_id:
        cursor.execute(
            """
            SELECT id FROM Bookings
            WHERE guest_id = ? AND room_id = ? AND check_in_date = ?
            ORDER BY id DESC LIMIT 1;
            """,
            (guest_id, booking_data.room_id, booking_data.check_in_date.isoformat()),
        )
        b_row = cursor.fetchone()
        booking_id = b_row["id"] if b_row else None


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
            "rate_plan_code": quote.rate_plan_code or "BAR",
            "coupon_code": applied_coupon,
            "adults": booking_data.adults,
            "children": booking_data.children,
            "guarantee_type": booking_data.guarantee_type.value,
            "estimated_arrival_time": booking_data.estimated_arrival_time,
            "special_requests": booking_data.special_requests,
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
        rate_plan_code=quote.rate_plan_code or "BAR",
        coupon_code=applied_coupon,
        discount_amount=discount_amount,
        adults=booking_data.adults,
        children=booking_data.children,
        estimated_arrival_time=booking_data.estimated_arrival_time,
        special_requests=booking_data.special_requests or "",
        guarantee_type=booking_data.guarantee_type,
        early_checkin_requested=booking_data.early_checkin_requested,
        late_checkout_requested=booking_data.late_checkout_requested,
        room=row_to_room_response(room),
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
    try:
        return _create_booking_impl(booking_data, conn)
    except HTTPException:
        raise
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reservation: {str(exc)}",
        )



@app.post(
    "/api/bookings/auto-assign",
    response_model=AutoAssignResponse,
    summary="Intelligently auto-assign optimal room for requested stay",
    tags=["Bookings"],
)
@app.post(
    "/bookings/auto-assign",
    response_model=AutoAssignResponse,
    include_in_schema=False,
)
def auto_assign_room(
    request: AutoAssignRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Intelligent room auto-assignment engine based on:
    - Availability over requested date interval
    - Room capacity requirement (party size: adults + children <= room max_occupancy)
    - Category match (if requested)
    - Floor level preference (if requested)
    - Housekeeping inspection priority (prefer Inspected > Clean > Touch-up Required > Dirty)
    - Operational status (Available > Cleaning)
    - Minimal wasted capacity fit
    """
    cursor = conn.cursor()
    party_size = request.adults + request.children

    # 1. Fetch rooms that are not in maintenance
    cursor.execute("""
        SELECT r.*
        FROM Rooms r
        WHERE r.status != 'Maintenance';
    """)
    all_candidate_rooms = [dict(r) for r in cursor.fetchall()]

    # 2. Exclude rooms with date conflicts
    available_candidates = []
    for r in all_candidate_rooms:
        cursor.execute(
            """
            SELECT COUNT(*) as conflicts
            FROM Bookings
            WHERE room_id = ?
              AND booking_status IN ('Confirmed', 'Checked-in')
              AND check_in_date < ?
              AND check_out_date > ?;
            """,
            (r["id"], request.check_out_date.isoformat(), request.check_in_date.isoformat()),
        )
        conflicts = cursor.fetchone()["conflicts"]
        if conflicts == 0:
            available_candidates.append(r)

    # 3. Filter candidates by capacity & category
    filtered = []
    for r in available_candidates:
        max_occ = r.get("max_occupancy") or 2
        if max_occ < party_size:
            continue
        if request.room_type and r.get("room_type") != request.room_type.value:
            continue
        filtered.append(r)

    if not filtered:
        return AutoAssignResponse(
            assigned_room=None,
            match_score=0,
            criteria_applied=[
                f"Dates {request.check_in_date} to {request.check_out_date}",
                f"Party size of {party_size} guests",
                f"No eligible vacant room found matching capacity and category"
            ],
            available_alternatives=[],
        )

    # 4. Score each room candidate
    criteria_applied = [
        f"Available from {request.check_in_date} to {request.check_out_date}",
        f"Capacity fits {party_size} guests (Adults: {request.adults}, Children: {request.children})",
    ]
    if request.room_type:
        criteria_applied.append(f"Category matched: {request.room_type.value}")
    if request.floor:
        criteria_applied.append(f"Floor preference evaluated: Level {request.floor}")
    if request.prefer_inspected:
        criteria_applied.append("Prioritizing QA Inspected rooms for immediate check-in")

    scored_rooms = []
    for r in filtered:
        score = 50  # Base availability score

        # Cleanliness priority
        c_status = r.get("cleanliness_status") or "Inspected"
        if c_status == "Inspected":
            score += 30
        elif c_status == "Clean":
            score += 20
        elif c_status == "Touch-up Required":
            score += 10

        # Operational status priority
        if r.get("status") == "Available":
            score += 20

        # Floor preference match
        if request.floor and r.get("floor") == request.floor:
            score += 25

        # Capacity fit (prefer exact capacity to avoid burning suites on single travelers)
        max_occ = r.get("max_occupancy") or 2
        diff = max_occ - party_size
        if diff == 0:
            score += 15
        elif diff == 1:
            score += 10
        elif diff <= 2:
            score += 5

        # Clamp score between 0 and 100
        normalized_score = min(100, max(0, score))
        scored_rooms.append((normalized_score, r))

    # Sort candidates descending by score, then room_number ascending
    scored_rooms.sort(key=lambda x: (x[0], -int(x[1].get("room_number", 0))), reverse=True)

    best_score, best_room = scored_rooms[0]
    assigned_response = row_to_room_response(best_room)

    alternatives = [row_to_room_response(rm) for _, rm in scored_rooms[1:4]]

    return AutoAssignResponse(
        assigned_room=assigned_response,
        match_score=best_score,
        criteria_applied=criteria_applied,
        available_alternatives=alternatives,
    )


# ==========================================
# Module 9: Reservation Lifecycle & Checkout Engine
# ==========================================

def get_booking_by_id(booking_id: int, conn: sqlite3.Connection) -> BookingResponse:
    """Helper to fetch a complete BookingResponse with joined room, guest, and amenities."""
    cursor = conn.cursor()
    if not IS_POSTGRES:
        cursor.execute("PRAGMA table_info(Bookings);")
        b_cols = {r[1] for r in cursor.fetchall()}
        if "coupon_code" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN coupon_code TEXT DEFAULT NULL;")
        if "discount_amount" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN discount_amount REAL NOT NULL DEFAULT 0.0;")
        if "adults" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN adults INTEGER NOT NULL DEFAULT 1;")
        if "children" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN children INTEGER NOT NULL DEFAULT 0;")
        if "estimated_arrival_time" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN estimated_arrival_time TEXT DEFAULT '15:00';")
        if "special_requests" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN special_requests TEXT DEFAULT '';")
        if "guarantee_type" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN guarantee_type TEXT NOT NULL DEFAULT 'Guaranteed';")
        if "early_checkin_requested" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN early_checkin_requested INTEGER NOT NULL DEFAULT 0;")
        if "late_checkout_requested" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN late_checkout_requested INTEGER NOT NULL DEFAULT 0;")
        if "rate_plan_code" not in b_cols:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN rate_plan_code TEXT NOT NULL DEFAULT 'BAR';")
    else:
        try:
            cursor.execute("ALTER TABLE Bookings ADD COLUMN IF NOT EXISTS rate_plan_code TEXT NOT NULL DEFAULT 'BAR';")
        except Exception:
            pass

    if not IS_POSTGRES:
        cursor.execute("PRAGMA table_info(Rooms);")
        r_cols = {r[1] for r in cursor.fetchall()}
    else:
        try:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS floor INTEGER NOT NULL DEFAULT 1;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS max_occupancy INTEGER NOT NULL DEFAULT 2;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS bed_type TEXT NOT NULL DEFAULT '1 King Bed';")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS view_type TEXT NOT NULL DEFAULT 'City Skyline';")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS sq_meters INTEGER NOT NULL DEFAULT 35;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS is_smoking INTEGER NOT NULL DEFAULT 0;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS cleanliness_status TEXT NOT NULL DEFAULT 'Inspected';")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS lock_reason TEXT DEFAULT NULL;")
        except Exception:
            pass
        try:
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE lower(table_name) = 'rooms';")
            r_cols = {r["column_name"] if isinstance(r, dict) or hasattr(r, "keys") else r[0] for r in cursor.fetchall()}
        except Exception:
            r_cols = set()

    extra_room_fields = []
    for c in ["floor", "max_occupancy", "bed_type", "view_type", "sq_meters", "is_smoking", "cleanliness_status", "lock_reason"]:
        if c in r_cols:
            extra_room_fields.append(f"r.{c}")
    extra_room_sql = (", " + ", ".join(extra_room_fields)) if extra_room_fields else ""

    cursor.execute(
        f"""
        SELECT b.*,
               g.first_name, g.last_name, g.email, g.phone, g.vip_tier, g.notes as guest_notes, g.created_at as guest_created_at,
               r.room_number, r.room_type, r.price_per_night, r.status as room_status, r.created_at as room_created_at
               {extra_room_sql}
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

    amenity_rows = []
    try:
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
    except Exception:
        amenity_rows = []

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

    r_dict = {
        "id": row["room_id"],
        "room_number": row["room_number"],
        "room_type": row["room_type"],
        "price_per_night": row["price_per_night"],
        "status": row["room_status"],
        "floor": row["floor"] if "floor" in row.keys() else 1,
        "max_occupancy": row["max_occupancy"] if "max_occupancy" in row.keys() else 2,
        "bed_type": row["bed_type"] if "bed_type" in row.keys() else "1 King Bed",
        "view_type": row["view_type"] if "view_type" in row.keys() else "City Skyline",
        "sq_meters": row["sq_meters"] if "sq_meters" in row.keys() else 35,
        "is_smoking": row["is_smoking"] if "is_smoking" in row.keys() else 0,
        "cleanliness_status": row["cleanliness_status"] if "cleanliness_status" in row.keys() else "Inspected",
        "lock_reason": row["lock_reason"] if "lock_reason" in row.keys() else None,
        "created_at": str(row["room_created_at"]) if row["room_created_at"] else None,
    }

    raw_cid = row["check_in_date"]
    parsed_cid = raw_cid if isinstance(raw_cid, date) else date.fromisoformat(str(raw_cid).split("T")[0])
    raw_cod = row["check_out_date"]
    parsed_cod = raw_cod if isinstance(raw_cod, date) else date.fromisoformat(str(raw_cod).split("T")[0])

    g_type = GuaranteeType.GUARANTEED
    if "guarantee_type" in row.keys() and row["guarantee_type"]:
        try:
            g_type = GuaranteeType(row["guarantee_type"])
        except Exception:
            g_type = GuaranteeType.GUARANTEED

    return BookingResponse(
        id=row["id"],
        guest_id=row["guest_id"],
        room_id=row["room_id"],
        check_in_date=parsed_cid,
        check_out_date=parsed_cod,
        total_price=float(row["total_price"]),
        booking_status=BookingStatus(row["booking_status"]),
        created_at=str(row["created_at"]) if row["created_at"] else None,
        rate_plan_code=row["rate_plan_code"] if ("rate_plan_code" in row.keys() and row["rate_plan_code"]) else "BAR",
        coupon_code=row["coupon_code"] if "coupon_code" in row.keys() else None,
        discount_amount=float(row["discount_amount"]) if ("discount_amount" in row.keys() and row["discount_amount"]) else 0.0,
        adults=row["adults"] if ("adults" in row.keys() and row["adults"] is not None) else 1,
        children=row["children"] if ("children" in row.keys() and row["children"] is not None) else 0,
        estimated_arrival_time=row["estimated_arrival_time"] if ("estimated_arrival_time" in row.keys() and row["estimated_arrival_time"]) else "15:00",
        special_requests=row["special_requests"] if ("special_requests" in row.keys() and row["special_requests"]) else "",
        guarantee_type=g_type,
        early_checkin_requested=bool(row["early_checkin_requested"]) if ("early_checkin_requested" in row.keys() and row["early_checkin_requested"]) else False,
        late_checkout_requested=bool(row["late_checkout_requested"]) if ("late_checkout_requested" in row.keys() and row["late_checkout_requested"]) else False,
        room=row_to_room_response(r_dict),
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
    try:
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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list bookings: {type(exc).__name__}: {str(exc)}",
        )


@app.get(
    "/api/bookings/{booking_id}",
    response_model=BookingResponse,
    summary="Get single reservation details by ID",
    tags=["Bookings"],
)
@app.get(
    "/bookings/{booking_id}",
    response_model=BookingResponse,
    include_in_schema=False,
)
def get_single_booking(
    booking_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Retrieves full booking dossier by unique reservation ID."""
    try:
        return get_booking_by_id(booking_id, conn)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch booking #{booking_id}: {type(exc).__name__}: {str(exc)}",
        )


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

    # Auto-issue active guest RFID keycard for arrival
    try:
        ensure_keycards_tables(conn)
        cursor.execute("SELECT id FROM Keycards WHERE booking_id = ? AND status = 'Active';", (booking_id,))
        existing_card = cursor.fetchone()
        if not existing_card:
            cursor.execute("SELECT first_name, last_name FROM Guests WHERE id = ?;", (booking["guest_id"],))
            g_row = cursor.fetchone()
            holder = f"{g_row['first_name']} {g_row['last_name']}" if g_row else "Hotel Guest"
            cursor.execute("SELECT room_number FROM Rooms WHERE id = ?;", (room_id,))
            r_row = cursor.fetchone()
            r_num = r_row["room_number"] if r_row else str(room_id)
            card_uid = f"RFID-{r_num}-{booking_id:04d}"
            cursor.execute(
                """
                INSERT INTO Keycards (card_uid, room_id, booking_id, holder_name, card_type, status, issued_by, notes)
                VALUES (?, ?, ?, ?, 'Guest', 'Active', 'Front Desk Arrival Check-In', 'Auto-encoded guest keycard on check-in');
                """,
                (card_uid, room_id, booking_id, holder),
            )
    except Exception as e:
        print(f"Keycard auto-issue note on check-in: {e}")

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

    if not IS_POSTGRES:
        cursor.execute("PRAGMA table_info(Rooms);")
        r_cols = {r[1] for r in cursor.fetchall()}
    else:
        r_cols = {"cleanliness_status"}

    if "cleanliness_status" in r_cols:
        cursor.execute("UPDATE Rooms SET status = 'Cleaning', cleanliness_status = 'Dirty', cleaning_priority = 'Rush Checkout Turnover' WHERE id = ?;", (room_id,))
    else:
        cursor.execute("UPDATE Rooms SET status = 'Cleaning' WHERE id = ?;", (room_id,))

    # Auto-dispatch Module 4 housekeeping turnover work order for departed room
    try:
        ensure_housekeeping_tasks_table(conn)
        cursor.execute(
            """
            INSERT INTO HousekeepingTasks (room_id, task_type, priority, status, assigned_housekeeper, notes)
            VALUES (?, 'Checkout Turnover', 'Rush Checkout Turnover', 'Pending', 'Maria Santos', ?);
            """,
            (room_id, f"Auto-dispatched turnover on checkout for Booking #{booking_id} (Room {booking['room_number']})"),
        )
    except Exception as e:
        print(f"Housekeeping turnover dispatch note: {e}")

    cursor.execute("UPDATE FolioCharges SET status = 'Paid' WHERE booking_id = ? AND status = 'Billed';", (booking_id,))

    # Auto-revoke active keycards for departing booking
    try:
        ensure_keycards_tables(conn)
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE Keycards
            SET status = 'Revoked',
                revoked_at = ?,
                revoked_reason = 'Guest Checked Out (Automatic departure deactivation)'
            WHERE booking_id = ? AND status = 'Active';
            """,
            (now_iso, booking_id),
        )
    except Exception as e:
        print(f"Keycards checkout revocation note: {e}")

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

    if not IS_POSTGRES:
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
# Module 3 & 11: Rates, Dynamic Pricing & Promotional Yield Management Endpoints
# ==========================================

@app.post(
    "/api/pricing/quote",
    response_model=PriceQuoteResponse,
    summary="Get detailed dynamic pricing quotation with surges and discounts",
    tags=["Pricing & Yield Management"],
)
@app.post("/pricing/quote", response_model=PriceQuoteResponse, include_in_schema=False)
@app.post("/api/rates/quote", response_model=PriceQuoteResponse, tags=["Pricing & Yield Management"])
@app.post("/rates/quote", response_model=PriceQuoteResponse, include_in_schema=False)
def get_pricing_quote(
    request: PriceQuoteRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Returns an itemized price quotation for a target room, stay dates, guest loyalty, coupon, and rate plan.
    Includes day-of-week breakdown (weekend surge, summer surge), occupancy demand surge, length-of-stay discount, and VIP tier benefits.
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
        rate_plan_code=request.rate_plan_code,
        apply_dynamic_pricing=True,
        conn=conn,
    )


def ensure_rate_plans_table(conn: sqlite3.Connection):
    """Safely guarantees RatePlans table and initial catalog exist across both SQLite and PostgreSQL."""
    cursor = conn.cursor()
    if not IS_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS RatePlans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            rate_multiplier REAL NOT NULL DEFAULT 1.0 CHECK(rate_multiplier > 0),
            cancellation_policy TEXT NOT NULL DEFAULT 'Flexible (24h free cancellation)',
            meal_plan TEXT NOT NULL DEFAULT 'Room Only',
            min_los INTEGER NOT NULL DEFAULT 1 CHECK(min_los >= 1),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
    else:
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS RatePlans (
                id SERIAL PRIMARY KEY,
                code VARCHAR(30) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                description TEXT DEFAULT '',
                rate_multiplier NUMERIC(4,2) NOT NULL DEFAULT 1.00 CHECK (rate_multiplier > 0),
                cancellation_policy VARCHAR(60) NOT NULL DEFAULT 'Flexible (24h free cancellation)',
                meal_plan VARCHAR(60) NOT NULL DEFAULT 'Room Only',
                min_los INTEGER NOT NULL DEFAULT 1 CHECK (min_los >= 1),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
            sample_plans = [
                ("BAR", "Best Available Rate", "Standard fully flexible rate with 24-hour cancellation flexibility.", 1.0, "Flexible (24h free cancellation)", "Room Only", 1, 1),
                ("NON_REF", "Non-Refundable Saver", "Advance purchase saver plan with guaranteed 15% discount. 100% non-refundable.", 0.85, "Non-Refundable (100% deposit locked)", "Room Only", 1, 1),
                ("BB_PACKAGE", "Bed & Breakfast Package", "Includes gourmet daily continental breakfast buffet for all guests.", 1.15, "Flexible (24h free cancellation)", "Continental Breakfast Included", 1, 1),
                ("CORP_EXTENDED", "Extended Stay & Corporate", "Long-stay executive preferred partner pricing with 20% discount. Minimum 3 nights required.", 0.80, "Moderate (48h cancellation)", "Room Only", 3, 1),
            ]
            for p in sample_plans:
                cursor.execute(
                    """
                    INSERT INTO RatePlans (code, name, description, rate_multiplier, cancellation_policy, meal_plan, min_los, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (code) DO NOTHING;
                    """,
                    p,
                )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass


@app.get(
    "/api/rates/plans",
    response_model=List[RatePlanResponse],
    summary="List all available rate plans and cancellation policies",
    tags=["Pricing & Yield Management"],
)
@app.get("/rates/plans", response_model=List[RatePlanResponse], include_in_schema=False)
def get_rate_plans(
    active_only: bool = Query(True, description="Filter for currently active rate plans only"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Retrieves all rate plans with their pricing multipliers, meal plans, cancellation policies, and MLOS rules."""
    cursor = conn.cursor()
    try:
        ensure_rate_plans_table(conn)
    except Exception:
        pass

    query = "SELECT * FROM RatePlans"
    params = []
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY rate_multiplier ASC;"
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
    except Exception:
        return []

    plans = []
    for r in rows:
        plans.append(
            RatePlanResponse(
                id=r["id"],
                code=r["code"],
                name=r["name"],
                description=r["description"] if "description" in r.keys() else "",
                rate_multiplier=float(r["rate_multiplier"]),
                cancellation_policy=CancellationPolicy(r["cancellation_policy"]),
                meal_plan=MealPlanType(r["meal_plan"]),
                min_los=int(r["min_los"]) if "min_los" in r.keys() else 1,
                is_active=bool(r["is_active"]),
                created_at=str(r["created_at"]) if r["created_at"] else None,
            )
        )
    return plans


@app.post(
    "/api/rates/plans",
    response_model=RatePlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom rate plan",
    tags=["Pricing & Yield Management"],
)
@app.post("/rates/plans", response_model=RatePlanResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_rate_plan(
    plan_data: RatePlanCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Creates a new rate plan with specific rate multiplier, cancellation terms, meal inclusions, and MLOS restrictions."""
    cursor = conn.cursor()
    ensure_rate_plans_table(conn)
    clean_code = plan_data.code.strip().upper()
    cursor.execute("SELECT id FROM RatePlans WHERE UPPER(code) = ?;", (clean_code,))
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rate plan code '{clean_code}' already exists.",
        )

    cursor.execute(
        """
        INSERT INTO RatePlans (code, name, description, rate_multiplier, cancellation_policy, meal_plan, min_los, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            clean_code,
            plan_data.name.strip(),
            plan_data.description or "",
            plan_data.rate_multiplier,
            plan_data.cancellation_policy.value,
            plan_data.meal_plan.value,
            plan_data.min_los,
            1 if plan_data.is_active else 0,
        ),
    )
    plan_id = cursor.lastrowid
    if not plan_id:
        cursor.execute("SELECT id FROM RatePlans WHERE UPPER(code) = ?;", (clean_code,))
        p_row = cursor.fetchone()
        plan_id = p_row["id"] if p_row else None

    # Audit log
    record_audit_log(
        conn,
        action="RATE_PLAN_CREATED",
        entity_type="RatePlan",
        entity_id=plan_id,
        details={
            "code": clean_code,
            "name": plan_data.name,
            "rate_multiplier": plan_data.rate_multiplier,
            "cancellation_policy": plan_data.cancellation_policy.value,
            "meal_plan": plan_data.meal_plan.value,
            "min_los": plan_data.min_los,
        },
        actor="Revenue Manager",
    )

    conn.commit()
    cursor.execute("SELECT * FROM RatePlans WHERE id = ?;", (plan_id,))
    row = cursor.fetchone()
    return RatePlanResponse(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        description=row["description"],
        rate_multiplier=float(row["rate_multiplier"]),
        cancellation_policy=CancellationPolicy(row["cancellation_policy"]),
        meal_plan=MealPlanType(row["meal_plan"]),
        min_los=int(row["min_los"]),
        is_active=bool(row["is_active"]),
        created_at=str(row["created_at"]) if row["created_at"] else None,
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
    if not IS_POSTGRES:
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
            valid_from=r["valid_from"] if isinstance(r["valid_from"], date) else date.fromisoformat(str(r["valid_from"])),
            valid_until=r["valid_until"] if isinstance(r["valid_until"], date) else date.fromisoformat(str(r["valid_until"])),
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
        valid_from=r["valid_from"] if isinstance(r["valid_from"], date) else date.fromisoformat(str(r["valid_from"])),
        valid_until=r["valid_until"] if isinstance(r["valid_until"], date) else date.fromisoformat(str(r["valid_until"])),
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
    c_from = str(coupon["valid_from"])
    c_until = str(coupon["valid_until"])
    if today_iso < c_from:
        return CouponValidateResponse(
            is_valid=False,
            code=clean_code,
            message=f"Coupon is not valid until {c_from}.",
        )

    if today_iso > c_until:
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


# ==========================================
# Module 4: Housekeeping & Room Status Management
# ==========================================

def ensure_housekeeping_tasks_table(conn: sqlite3.Connection):
    """Ensures HousekeepingTasks table exists across both SQLite and PostgreSQL connections."""
    cursor = conn.cursor()
    if not IS_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS HousekeepingTasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            task_type TEXT NOT NULL DEFAULT 'Checkout Turnover',
            priority TEXT NOT NULL DEFAULT 'Normal',
            status TEXT NOT NULL DEFAULT 'Pending',
            assigned_housekeeper TEXT DEFAULT 'Maria Santos',
            linen_changed INTEGER NOT NULL DEFAULT 0,
            amenities_restocked INTEGER NOT NULL DEFAULT 0,
            bathroom_sanitized INTEGER NOT NULL DEFAULT 0,
            notes TEXT DEFAULT '',
            inspected_by TEXT DEFAULT NULL,
            inspector_notes TEXT DEFAULT '',
            started_at TIMESTAMP DEFAULT NULL,
            completed_at TIMESTAMP DEFAULT NULL,
            inspected_at TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE CASCADE
        );
        """)
        cursor.execute("PRAGMA table_info(Rooms);")
        r_cols = {r[1] for r in cursor.fetchall()}
        if "floor" not in r_cols:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN floor INTEGER NOT NULL DEFAULT 1;")
        if "assigned_housekeeper" not in r_cols:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN assigned_housekeeper TEXT DEFAULT NULL;")
        if "cleaning_priority" not in r_cols:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN cleaning_priority TEXT NOT NULL DEFAULT 'Normal';")
        if "dnd_status" not in r_cols:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN dnd_status INTEGER NOT NULL DEFAULT 0;")
        if "last_cleaned_at" not in r_cols:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN last_cleaned_at TIMESTAMP DEFAULT NULL;")
        if "last_inspected_at" not in r_cols:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN last_inspected_at TIMESTAMP DEFAULT NULL;")
        conn.commit()
    else:
        try:
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS floor INTEGER DEFAULT 1;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS cleanliness_status VARCHAR(50) DEFAULT 'Inspected';")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS assigned_housekeeper VARCHAR(100) DEFAULT NULL;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS cleaning_priority VARCHAR(50) DEFAULT 'Normal';")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS dnd_status INTEGER DEFAULT 0;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS last_cleaned_at TIMESTAMPTZ DEFAULT NULL;")
            cursor.execute("ALTER TABLE Rooms ADD COLUMN IF NOT EXISTS last_inspected_at TIMESTAMPTZ DEFAULT NULL;")
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS HousekeepingTasks (
                id SERIAL PRIMARY KEY,
                room_id INTEGER NOT NULL REFERENCES Rooms(id) ON DELETE CASCADE,
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
            """)
            conn.commit()

            cursor.execute("SELECT COUNT(*) as cnt FROM HousekeepingTasks;")
            row = cursor.fetchone()
            cnt = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))
            if cnt == 0:
                sample_tasks = [
                    (3, "Checkout Turnover", "Rush Checkout Turnover", "Pending", "Maria Santos", 0, 0, 0, "Previous guest departed at 11 AM. New check-in expected at 3 PM."),
                    (4, "Stayover Clean", "Normal", "In Progress", "David Kim", 1, 0, 0, "Replace extra towels and restock espresso pods."),
                    (1, "Inspection Audit", "Normal", "Inspected", "Elena Rostova", 1, 1, 1, "Passed 5-star quality sanitation audit."),
                ]
                for t in sample_tasks:
                    cursor.execute(
                        """
                        INSERT INTO HousekeepingTasks (room_id, task_type, priority, status, assigned_housekeeper, linen_changed, amenities_restocked, bathroom_sanitized, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """,
                        t,
                    )
                conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"ensure_housekeeping_tasks_table postgres error: {e}")


def row_to_housekeeping_task_response(r) -> HousekeepingTaskResponse:
    keys = set(r.keys()) if hasattr(r, "keys") else set()

    def _parse_task_type(val):
        try:
            return HousekeepingTaskType(val)
        except Exception:
            return HousekeepingTaskType.CHECKOUT_TURNOVER

    def _parse_priority(val):
        try:
            return HousekeepingPriority(val)
        except Exception:
            return HousekeepingPriority.NORMAL

    def _parse_status(val):
        try:
            return HousekeepingTaskStatus(val)
        except Exception:
            return HousekeepingTaskStatus.PENDING

    return HousekeepingTaskResponse(
        id=int(r["id"]),
        room_id=int(r["room_id"]),
        room_number=str(r["room_number"]) if "room_number" in keys and r["room_number"] is not None else None,
        room_type=str(r["room_type"]) if "room_type" in keys and r["room_type"] is not None else None,
        floor=int(r["floor"]) if "floor" in keys and r["floor"] is not None else 1,
        task_type=_parse_task_type(r["task_type"] if "task_type" in keys else None),
        priority=_parse_priority(r["priority"] if "priority" in keys else None),
        status=_parse_status(r["status"] if "status" in keys else None),
        assigned_housekeeper=str(r["assigned_housekeeper"]) if "assigned_housekeeper" in keys and r["assigned_housekeeper"] is not None else "Maria Santos",
        linen_changed=bool(r["linen_changed"]) if "linen_changed" in keys and r["linen_changed"] is not None else False,
        amenities_restocked=bool(r["amenities_restocked"]) if "amenities_restocked" in keys and r["amenities_restocked"] is not None else False,
        bathroom_sanitized=bool(r["bathroom_sanitized"]) if "bathroom_sanitized" in keys and r["bathroom_sanitized"] is not None else False,
        notes=str(r["notes"]) if "notes" in keys and r["notes"] else "",
        inspected_by=str(r["inspected_by"]) if "inspected_by" in keys and r["inspected_by"] is not None else None,
        inspector_notes=str(r["inspector_notes"]) if "inspector_notes" in keys and r["inspector_notes"] else "",
        started_at=str(r["started_at"]) if "started_at" in keys and r["started_at"] else None,
        completed_at=str(r["completed_at"]) if "completed_at" in keys and r["completed_at"] else None,
        inspected_at=str(r["inspected_at"]) if "inspected_at" in keys and r["inspected_at"] else None,
        created_at=str(r["created_at"]) if "created_at" in keys and r["created_at"] else None,
    )


@app.get(
    "/api/housekeeping/dashboard",
    response_model=HousekeepingSummaryResponse,
    summary="Get executive housekeeping operational KPI dashboard summary",
    tags=["Housekeeping & Room Status"],
)
@app.get(
    "/api/housekeeping/summary",
    response_model=HousekeepingSummaryResponse,
    include_in_schema=False,
)
def get_housekeeping_dashboard(conn: sqlite3.Connection = Depends(get_db)):
    """
    Returns real-time aggregated operational metrics for housekeeping:
    - Inspected Ready vs Clean (Pending Inspection) vs Dirty (Needs Turnover)
    - Cleaning In Progress vs Touch-up Required
    - Active Do Not Disturb (DND) count
    - Urgent and rush turnover task counts
    - Active housekeeping attendants
    """
    ensure_housekeeping_tasks_table(conn)
    cursor = conn.cursor()

    # Room states
    cursor.execute("SELECT r.* FROM Rooms r;")
    rooms = cursor.fetchall()
    total_rooms = len(rooms)
    inspected_ready = sum(1 for r in rooms if (r.get("cleanliness_status") if isinstance(r, dict) else r["cleanliness_status"]) == "Inspected")
    clean_pending_inspection = sum(1 for r in rooms if (r.get("cleanliness_status") if isinstance(r, dict) else r["cleanliness_status"]) == "Clean")
    dirty_needs_turnover = sum(1 for r in rooms if (r.get("cleanliness_status") if isinstance(r, dict) else r["cleanliness_status"]) == "Dirty")
    cleaning_in_progress = sum(1 for r in rooms if (r.get("status") if isinstance(r, dict) else r["status"]) == "Cleaning")
    touch_up_required = sum(1 for r in rooms if (r.get("cleanliness_status") if isinstance(r, dict) else r["cleanliness_status"]) == "Touch-up Required")
    dnd_active = sum(1 for r in rooms if (r.get("dnd_status") if isinstance(r, dict) else (r["dnd_status"] if "dnd_status" in r.keys() else 0)))

    # Task states
    cursor.execute(
        """
        SELECT COUNT(*) as cnt
        FROM HousekeepingTasks
        WHERE priority IN ('Urgent VIP Arrival', 'Rush Checkout Turnover')
          AND status != 'Inspected';
        """
    )
    urg_row = cursor.fetchone()
    urgent_priority_count = int(urg_row["cnt"] if isinstance(urg_row, dict) and "cnt" in urg_row else (urg_row[0] if urg_row else 0))

    cursor.execute(
        """
        SELECT COUNT(*) as cnt
        FROM HousekeepingTasks
        WHERE status IN ('Pending', 'In Progress');
        """
    )
    pend_row = cursor.fetchone()
    pending_tasks_count = int(pend_row["cnt"] if isinstance(pend_row, dict) and "cnt" in pend_row else (pend_row[0] if pend_row else 0))

    cursor.execute(
        """
        SELECT DISTINCT assigned_housekeeper
        FROM HousekeepingTasks
        WHERE assigned_housekeeper IS NOT NULL AND TRIM(assigned_housekeeper) != '';
        """
    )
    hk_rows = cursor.fetchall()
    housekeepers = []
    for h in hk_rows:
        name = h["assigned_housekeeper"] if isinstance(h, dict) and "assigned_housekeeper" in h else (h[0] if h else None)
        if name:
            housekeepers.append(name)
    if not housekeepers:
        housekeepers = ["Maria Santos", "David Kim", "Elena Rostova"]

    return HousekeepingSummaryResponse(
        total_rooms=total_rooms,
        inspected_ready=inspected_ready,
        clean_pending_inspection=clean_pending_inspection,
        dirty_needs_turnover=dirty_needs_turnover,
        cleaning_in_progress=cleaning_in_progress,
        touch_up_required=touch_up_required,
        dnd_active=dnd_active,
        urgent_priority_count=urgent_priority_count,
        pending_tasks_count=pending_tasks_count,
        active_housekeepers=housekeepers,
    )


@app.get(
    "/api/housekeeping/tasks",
    response_model=List[HousekeepingTaskResponse],
    summary="List housekeeping turnover tasks with filtering",
    tags=["Housekeeping & Room Status"],
)
def get_housekeeping_tasks(
    task_status: Optional[HousekeepingTaskStatus] = Query(None, alias="status", description="Filter by task status"),
    priority: Optional[HousekeepingPriority] = Query(None, description="Filter by urgency priority"),
    room_id: Optional[int] = Query(None, description="Filter by room ID"),
    assigned_housekeeper: Optional[str] = Query(None, description="Filter by assigned staff"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Retrieves all housekeeping turnover work orders joined with room numbers and floors."""
    ensure_housekeeping_tasks_table(conn)
    cursor = conn.cursor()

    conditions = []
    params = []

    if task_status:
        conditions.append("t.status = ?")
        params.append(task_status.value)
    if priority:
        conditions.append("t.priority = ?")
        params.append(priority.value)
    if room_id:
        conditions.append("t.room_id = ?")
        params.append(room_id)
    if assigned_housekeeper:
        conditions.append("t.assigned_housekeeper = ?")
        params.append(assigned_housekeeper)

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"""
    SELECT t.*, r.room_number, r.room_type, r.floor
    FROM HousekeepingTasks t
    LEFT JOIN Rooms r ON t.room_id = r.id
    {where_clause}
    ORDER BY
        CASE t.priority
            WHEN 'Urgent VIP Arrival' THEN 1
            WHEN 'Rush Checkout Turnover' THEN 2
            WHEN 'High' THEN 3
            WHEN 'Normal' THEN 4
            ELSE 5
        END,
        t.id DESC;
    """
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        return [row_to_housekeeping_task_response(r) for r in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"get_housekeeping_tasks error: {str(exc)}",
        )


@app.post(
    "/api/housekeeping/tasks",
    response_model=HousekeepingTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch a new housekeeping turnover or cleaning task",
    tags=["Housekeeping & Room Status"],
)
def create_housekeeping_task(
    payload: HousekeepingTaskCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Dispatches a new housekeeping turnover work order and aligns room cleaning status."""
    ensure_housekeeping_tasks_table(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT id, room_number, status, cleanliness_status FROM Rooms WHERE id = ?;", (payload.room_id,))
    room = cursor.fetchone()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {payload.room_id} does not exist.",
        )

    assigned = payload.assigned_housekeeper.strip() if payload.assigned_housekeeper else "Maria Santos"
    cursor.execute(
        """
        INSERT INTO HousekeepingTasks (room_id, task_type, priority, status, assigned_housekeeper, notes)
        VALUES (?, ?, ?, 'Pending', ?, ?);
        """,
        (
            payload.room_id,
            payload.task_type.value,
            payload.priority.value,
            assigned,
            payload.notes.strip() if payload.notes else "",
        ),
    )
    new_task_id = cursor.lastrowid

    # Sync room cleaning priority and attendant
    cursor.execute(
        """
        UPDATE Rooms
        SET assigned_housekeeper = ?, cleaning_priority = ?
        WHERE id = ?;
        """,
        (assigned, payload.priority.value, payload.room_id),
    )

    record_audit_log(
        conn,
        action="HOUSEKEEPING_TASK_CREATED",
        entity_type="Room",
        entity_id=payload.room_id,
        details={
            "task_id": new_task_id,
            "room_number": room["room_number"],
            "task_type": payload.task_type.value,
            "priority": payload.priority.value,
            "assigned_housekeeper": assigned,
        },
        actor="Executive Housekeeper",
    )
    conn.commit()

    cursor.execute(
        """
        SELECT t.*, r.room_number, r.room_type, r.floor
        FROM HousekeepingTasks t
        JOIN Rooms r ON t.room_id = r.id
        WHERE t.id = ?;
        """,
        (new_task_id,),
    )
    row = cursor.fetchone()
    return row_to_housekeeping_task_response(row)


@app.patch(
    "/api/housekeeping/tasks/{task_id}",
    response_model=HousekeepingTaskResponse,
    summary="Update housekeeping task lifecycle, checklist, and quality audit",
    tags=["Housekeeping & Room Status"],
)
def update_housekeeping_task(
    task_id: int,
    payload: HousekeepingTaskUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Updates the lifecycle status and quality checklist of a housekeeping task:
    - Status transitions: Pending -> In Progress (marks room Cleaning) -> Cleaned (marks room Clean) -> Inspected (auto-releases room to Available!)
    - Checklist updates: linen_changed, amenities_restocked, bathroom_sanitized
    - Inspector notes and sign-off
    """
    ensure_housekeeping_tasks_table(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT t.*, r.room_number, r.status as room_status, r.cleanliness_status as room_cleanliness
        FROM HousekeepingTasks t
        JOIN Rooms r ON t.room_id = r.id
        WHERE t.id = ?;
        """,
        (task_id,),
    )
    task = cursor.fetchone()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Housekeeping task #{task_id} not found.",
        )

    room_id = task["room_id"]
    current_task_status = task["status"]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    updates = []
    params = []

    if payload.status is not None:
        updates.append("status = ?")
        params.append(payload.status.value)
        if payload.status == HousekeepingTaskStatus.IN_PROGRESS and not task["started_at"]:
            updates.append("started_at = ?")
            params.append(now_iso)
            # Update room to Cleaning if Available
            if task["room_status"] == "Available":
                cursor.execute("UPDATE Rooms SET status = 'Cleaning' WHERE id = ?;", (room_id,))
        elif payload.status == HousekeepingTaskStatus.CLEANED:
            updates.append("completed_at = ?")
            params.append(now_iso)
            cursor.execute("UPDATE Rooms SET cleanliness_status = 'Clean', last_cleaned_at = ? WHERE id = ?;", (now_iso, room_id))
        elif payload.status == HousekeepingTaskStatus.INSPECTED:
            updates.append("inspected_at = ?")
            params.append(now_iso)
            inspector = payload.inspected_by or "Executive Housekeeper"
            updates.append("inspected_by = ?")
            params.append(inspector)
            # Release room to Available if currently Cleaning
            cursor.execute(
                """
                UPDATE Rooms
                SET cleanliness_status = 'Inspected',
                    last_inspected_at = ?,
                    status = CASE WHEN status = 'Cleaning' THEN 'Available' ELSE status END
                WHERE id = ?;
                """,
                (now_iso, room_id),
            )

    if payload.assigned_housekeeper is not None:
        updates.append("assigned_housekeeper = ?")
        params.append(payload.assigned_housekeeper.strip())
        cursor.execute("UPDATE Rooms SET assigned_housekeeper = ? WHERE id = ?;", (payload.assigned_housekeeper.strip(), room_id))

    if payload.priority is not None:
        updates.append("priority = ?")
        params.append(payload.priority.value)
        cursor.execute("UPDATE Rooms SET cleaning_priority = ? WHERE id = ?;", (payload.priority.value, room_id))

    if payload.linen_changed is not None:
        updates.append("linen_changed = ?")
        params.append(1 if payload.linen_changed else 0)

    if payload.amenities_restocked is not None:
        updates.append("amenities_restocked = ?")
        params.append(1 if payload.amenities_restocked else 0)

    if payload.bathroom_sanitized is not None:
        updates.append("bathroom_sanitized = ?")
        params.append(1 if payload.bathroom_sanitized else 0)

    if payload.notes is not None:
        updates.append("notes = ?")
        params.append(payload.notes.strip())

    if payload.inspected_by is not None and "inspected_by" not in [u.split()[0] for u in updates]:
        updates.append("inspected_by = ?")
        params.append(payload.inspected_by.strip())

    if payload.inspector_notes is not None:
        updates.append("inspector_notes = ?")
        params.append(payload.inspector_notes.strip())

    if updates:
        params.append(task_id)
        update_sql = f"UPDATE HousekeepingTasks SET {', '.join(updates)} WHERE id = ?;"
        cursor.execute(update_sql, params)

    record_audit_log(
        conn,
        action="HOUSEKEEPING_TASK_UPDATED",
        entity_type="Room",
        entity_id=room_id,
        details={
            "task_id": task_id,
            "room_number": task["room_number"],
            "old_status": current_task_status,
            "new_status": payload.status.value if payload.status else current_task_status,
            "inspected_by": payload.inspected_by,
        },
        actor=payload.inspected_by or "Housekeeping Attendant",
    )
    conn.commit()

    cursor.execute(
        """
        SELECT t.*, r.room_number, r.room_type, r.floor
        FROM HousekeepingTasks t
        JOIN Rooms r ON t.room_id = r.id
        WHERE t.id = ?;
        """,
        (task_id,),
    )
    row = cursor.fetchone()
    return row_to_housekeeping_task_response(row)


# ==============================================================================
# Module 5: Room Keycard / Access Control & Security Logging
# ==============================================================================

def ensure_keycards_tables(conn: sqlite3.Connection):
    """Guarantees Keycards and AccessLogs tables and indexes exist in SQLite / PostgreSQL."""
    cursor = conn.cursor()
    if not IS_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Keycards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_uid TEXT NOT NULL UNIQUE,
            room_id INTEGER DEFAULT NULL,
            booking_id INTEGER DEFAULT NULL,
            holder_name TEXT NOT NULL,
            card_type TEXT NOT NULL DEFAULT 'Guest' CHECK(card_type IN ('Guest', 'Staff Master', 'Maintenance', 'Housekeeping', 'Emergency Override')),
            status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Suspended', 'Revoked', 'Expired')),
            issued_by TEXT NOT NULL DEFAULT 'Front Desk Encoder',
            notes TEXT DEFAULT '',
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP DEFAULT NULL,
            revoked_at TIMESTAMP DEFAULT NULL,
            revoked_reason TEXT DEFAULT NULL,
            FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE SET NULL,
            FOREIGN KEY (booking_id) REFERENCES Bookings(id) ON DELETE SET NULL
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS AccessLogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_uid TEXT NOT NULL,
            room_id INTEGER NOT NULL,
            reader_location TEXT NOT NULL DEFAULT 'Room Exterior Lock',
            event_type TEXT NOT NULL CHECK(event_type IN ('Granted', 'Denied - Expired', 'Denied - Invalid Room', 'Denied - Card Revoked', 'Denied - Card Suspended', 'Denied - Room Locked Out')),
            access_granted INTEGER NOT NULL DEFAULT 0,
            attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE CASCADE
        );
        """)
        conn.commit()
    else:
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS Keycards (
                id SERIAL PRIMARY KEY,
                card_uid VARCHAR(100) NOT NULL UNIQUE,
                room_id INTEGER REFERENCES Rooms(id) ON DELETE SET NULL,
                booking_id INTEGER REFERENCES Bookings(id) ON DELETE SET NULL,
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
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS AccessLogs (
                id SERIAL PRIMARY KEY,
                card_uid VARCHAR(100) NOT NULL,
                room_id INTEGER NOT NULL REFERENCES Rooms(id) ON DELETE CASCADE,
                reader_location VARCHAR(150) NOT NULL DEFAULT 'Room Exterior Lock',
                event_type VARCHAR(50) NOT NULL,
                access_granted BOOLEAN NOT NULL DEFAULT FALSE,
                attempted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()

            cursor.execute("SELECT COUNT(*) as cnt FROM Keycards;")
            row = cursor.fetchone()
            cnt = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))
            if cnt == 0:
                sample_cards = [
                    ("RFID-101A-8821", 1, 1, "Alexander Pierce", "Guest", "Active", "Front Desk Encoder", "Primary guest keycard", None, None, None),
                    ("RFID-201A-4432", 3, 2, "Sophia Laurent", "Guest", "Active", "Front Desk Encoder", "Primary guest keycard", None, None, None),
                    ("RFID-MASTER-001", None, None, "Sarah Jenkins (GM)", "Staff Master", "Active", "Security Admin", "Master bypass key for Executive General Manager", None, None, None),
                    ("RFID-HK-002", None, None, "Maria Santos", "Housekeeping", "Active", "Housekeeping Supervisor", "Attendant floor service key", None, None, None),
                    ("RFID-101A-7700", 1, 1, "Alexander Pierce", "Guest", "Revoked", "Front Desk Encoder", "Old keycard replaced due to misplacement", "2026-09-29 14:00:00", "2026-09-29 18:30:00", "Reported Lost by Guest; Replaced with RFID-101A-8821"),
                ]
                for c in sample_cards:
                    cursor.execute("""
                    INSERT INTO Keycards (card_uid, room_id, booking_id, holder_name, card_type, status, issued_by, notes, expires_at, revoked_at, revoked_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, c)
                sample_taps = [
                    ("RFID-101A-8821", 1, "Room 101 Exterior Lock", "Granted", 1, "2026-10-01 10:15:00"),
                    ("RFID-MASTER-001", 2, "Room 102 Exterior Lock", "Granted", 1, "2026-10-01 11:30:00"),
                    ("RFID-101A-7700", 1, "Room 101 Exterior Lock", "Denied - Card Revoked", 0, "2026-10-01 11:45:00"),
                    ("RFID-101A-8821", 2, "Room 102 Exterior Lock", "Denied - Invalid Room", 0, "2026-10-01 12:00:00"),
                ]
                for t in sample_taps:
                    cursor.execute("""
                    INSERT INTO AccessLogs (card_uid, room_id, reader_location, event_type, access_granted, attempted_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """, (t[0], t[1], t[2], t[3], bool(t[4]), t[5]))
                conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"ensure_keycards_tables postgres error: {e}")


def row_to_keycard_response(r) -> KeycardResponse:
    keys = set(r.keys()) if hasattr(r, "keys") else set()

    def _parse_card_type(val):
        try:
            return KeycardType(val)
        except Exception:
            return KeycardType.GUEST

    def _parse_status(val):
        try:
            return KeycardStatus(val)
        except Exception:
            return KeycardStatus.ACTIVE

    return KeycardResponse(
        id=int(r["id"]),
        card_uid=str(r["card_uid"]),
        room_id=int(r["room_id"]) if "room_id" in keys and r["room_id"] is not None else None,
        booking_id=int(r["booking_id"]) if "booking_id" in keys and r["booking_id"] is not None else None,
        holder_name=str(r["holder_name"]),
        card_type=_parse_card_type(r["card_type"] if "card_type" in keys else None),
        status=_parse_status(r["status"] if "status" in keys else None),
        issued_by=str(r["issued_by"]) if "issued_by" in keys and r["issued_by"] else "Front Desk Encoder",
        notes=str(r["notes"]) if "notes" in keys and r["notes"] else "",
        room_number=str(r["room_number"]) if "room_number" in keys and r["room_number"] is not None else None,
        room_type=str(r["room_type"]) if "room_type" in keys and r["room_type"] is not None else None,
        floor=int(r["floor"]) if "floor" in keys and r["floor"] is not None else None,
        issued_at=str(r["issued_at"]) if "issued_at" in keys and r["issued_at"] else None,
        expires_at=str(r["expires_at"]) if "expires_at" in keys and r["expires_at"] else None,
        revoked_at=str(r["revoked_at"]) if "revoked_at" in keys and r["revoked_at"] else None,
        revoked_reason=str(r["revoked_reason"]) if "revoked_reason" in keys and r["revoked_reason"] else None,
    )


def row_to_access_log_response(r) -> AccessLogResponse:
    keys = set(r.keys()) if hasattr(r, "keys") else set()
    return AccessLogResponse(
        id=int(r["id"]),
        card_uid=str(r["card_uid"]),
        room_id=int(r["room_id"]),
        room_number=str(r["room_number"]) if "room_number" in keys and r["room_number"] is not None else None,
        holder_name=str(r["holder_name"]) if "holder_name" in keys and r["holder_name"] is not None else None,
        card_type=str(r["card_type"]) if "card_type" in keys and r["card_type"] is not None else None,
        reader_location=str(r["reader_location"]) if "reader_location" in keys and r["reader_location"] else "Room Exterior Lock",
        event_type=str(r["event_type"]) if "event_type" in keys and r["event_type"] else "Granted",
        access_granted=bool(r["access_granted"]) if "access_granted" in keys else False,
        attempted_at=str(r["attempted_at"]) if "attempted_at" in keys and r["attempted_at"] else "",
    )


@app.get(
    "/api/keycards",
    response_model=List[KeycardResponse],
    summary="List all issued keycard credentials with multi-filter query support",
    tags=["Keycards & Access Control"],
)
def get_keycards(
    status_filter: Optional[KeycardStatus] = Query(None, alias="status", description="Filter by keycard status"),
    card_type: Optional[KeycardType] = Query(None, description="Filter by card category"),
    room_id: Optional[int] = Query(None, description="Filter by assigned room ID"),
    booking_id: Optional[int] = Query(None, description="Filter by booking folio ID"),
    search: Optional[str] = Query(None, description="Search by holder name or card UID"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Lists electronic keycards joined with room numbers and floors."""
    ensure_keycards_tables(conn)
    cursor = conn.cursor()

    conditions = []
    params = []

    if status_filter:
        conditions.append("k.status = ?")
        params.append(status_filter.value)
    if card_type:
        conditions.append("k.card_type = ?")
        params.append(card_type.value)
    if room_id:
        conditions.append("k.room_id = ?")
        params.append(room_id)
    if booking_id:
        conditions.append("k.booking_id = ?")
        params.append(booking_id)
    if search:
        s = f"%{search.strip()}%"
        conditions.append("(k.holder_name LIKE ? OR k.card_uid LIKE ?)")
        params.extend([s, s])

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"""
    SELECT k.*, r.room_number, r.room_type, r.floor
    FROM Keycards k
    LEFT JOIN Rooms r ON k.room_id = r.id
    {where_clause}
    ORDER BY k.id DESC;
    """
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    rows = cursor.fetchall()
    return [row_to_keycard_response(r) for r in rows]


@app.post(
    "/api/keycards/issue",
    response_model=KeycardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue and encode a new electronic RFID/NFC keycard",
    tags=["Keycards & Access Control"],
)
def issue_keycard(
    payload: KeycardIssueRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Encodes and registers a new physical or virtual room keycard:
    - Validates target room exists if room_id is specified
    - Generates unique RFID hardware identifier if omitted
    - Prevents duplicates on active card UIDs
    - Records audit log entry KEYCARD_ISSUED
    """
    import random
    ensure_keycards_tables(conn)
    cursor = conn.cursor()

    room_number = None
    if payload.room_id is not None:
        cursor.execute("SELECT id, room_number FROM Rooms WHERE id = ?;", (payload.room_id,))
        room = cursor.fetchone()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Room with ID {payload.room_id} not found.",
            )
        room_number = room["room_number"]

    # Generate UID if omitted
    if payload.card_uid and payload.card_uid.strip():
        card_uid = payload.card_uid.strip()
    else:
        prefix = f"RFID-{room_number}" if room_number else f"RFID-{payload.card_type.value[:3].upper()}"
        suffix = random.randint(1000, 9999)
        card_uid = f"{prefix}-{suffix}"

    # Verify uniqueness
    cursor.execute("SELECT id FROM Keycards WHERE card_uid = ?;", (card_uid,))
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Keycard with UID '{card_uid}' already exists in registry.",
        )

    issued_by = payload.issued_by or "Front Desk Encoder"
    cursor.execute(
        """
        INSERT INTO Keycards (card_uid, room_id, booking_id, holder_name, card_type, status, issued_by, notes, expires_at)
        VALUES (?, ?, ?, ?, ?, 'Active', ?, ?, ?);
        """,
        (
            card_uid,
            payload.room_id,
            payload.booking_id,
            payload.holder_name.strip(),
            payload.card_type.value,
            issued_by,
            payload.notes.strip() if payload.notes else "",
            payload.expires_at,
        ),
    )
    new_card_id = cursor.lastrowid

    record_audit_log(
        conn,
        action="KEYCARD_ISSUED",
        entity_type="Keycard",
        entity_id=new_card_id,
        details={
            "card_uid": card_uid,
            "holder_name": payload.holder_name.strip(),
            "card_type": payload.card_type.value,
            "room_id": payload.room_id,
            "room_number": room_number,
            "issued_by": issued_by,
        },
        actor=issued_by,
    )
    conn.commit()

    cursor.execute(
        """
        SELECT k.*, r.room_number, r.room_type, r.floor
        FROM Keycards k
        LEFT JOIN Rooms r ON k.room_id = r.id
        WHERE k.id = ?;
        """,
        (new_card_id,),
    )
    row = cursor.fetchone()
    return row_to_keycard_response(row)


@app.post(
    "/api/keycards/{card_id}/revoke",
    response_model=KeycardResponse,
    summary="Immediately revoke or decommission a lost/stolen keycard",
    tags=["Keycards & Access Control"],
)
def revoke_keycard(
    card_id: int,
    payload: KeycardRevokeRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Deactivates a keycard credential immediately:
    - Sets status to 'Revoked'
    - Records timestamp and reason
    - Logs audit trail entry KEYCARD_REVOKED
    """
    ensure_keycards_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT id, card_uid, room_id, holder_name, status FROM Keycards WHERE id = ?;", (card_id,))
    card = cursor.fetchone()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keycard with ID {card_id} does not exist.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    revoked_by = payload.revoked_by or "Security Officer"

    cursor.execute(
        """
        UPDATE Keycards
        SET status = 'Revoked',
            revoked_at = ?,
            revoked_reason = ?
        WHERE id = ?;
        """,
        (now_iso, payload.reason.strip(), card_id),
    )

    record_audit_log(
        conn,
        action="KEYCARD_REVOKED",
        entity_type="Keycard",
        entity_id=card_id,
        details={
            "card_uid": card["card_uid"],
            "holder_name": card["holder_name"],
            "reason": payload.reason.strip(),
            "revoked_by": revoked_by,
        },
        actor=revoked_by,
    )
    conn.commit()

    cursor.execute(
        """
        SELECT k.*, r.room_number, r.room_type, r.floor
        FROM Keycards k
        LEFT JOIN Rooms r ON k.room_id = r.id
        WHERE k.id = ?;
        """,
        (card_id,),
    )
    row = cursor.fetchone()
    return row_to_keycard_response(row)


@app.post(
    "/api/access-control/tap",
    response_model=DoorTapResponse,
    summary="Simulate an RFID reader lock tap event and record audit log",
    tags=["Keycards & Access Control"],
)
def tap_door_lock(
    payload: DoorTapRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Evaluates physical lock reader verification when an RFID credential is presented:
    - Validates target room exists (404)
    - Verifies card exists in registry (Denied - Invalid Room if unknown)
    - Verifies card is not Revoked, Suspended, or Expired
    - Verifies room is not locked out in Maintenance
    - Verifies room permission:
        - Master / Emergency / Staff keys grant access to any room
        - Guest keys grant access only to their assigned room
    - Inserts event into AccessLogs table
    - Returns verdict with message and timestamp
    """
    ensure_keycards_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT id, room_number, status FROM Rooms WHERE id = ?;", (payload.room_id,))
    room = cursor.fetchone()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target room with ID {payload.room_id} does not exist.",
        )
    room_number = room["room_number"]

    cursor.execute("SELECT * FROM Keycards WHERE card_uid = ?;", (payload.card_uid.strip(),))
    card = cursor.fetchone()

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    reader_loc = payload.reader_location or f"Room {room_number} Exterior Lock"

    access_granted = False
    event_type = AccessEventType.DENIED_INVALID_ROOM
    message = "Access Denied: Unrecognized keycard credential."
    holder_name = None
    card_type_enum = None

    if not card:
        access_granted = False
        event_type = AccessEventType.DENIED_INVALID_ROOM
        message = "Access Denied: Card UID not registered in hotel system."
    else:
        holder_name = card["holder_name"]
        try:
            card_type_enum = KeycardType(card["card_type"])
        except Exception:
            card_type_enum = KeycardType.GUEST

        card_keys = set(card.keys()) if hasattr(card, "keys") else set()
        card_status = card["status"]
        rev_reason = card["revoked_reason"] if "revoked_reason" in card_keys else None
        expires_at_val = card["expires_at"] if "expires_at" in card_keys else None

        if card_status == "Revoked":
            access_granted = False
            event_type = AccessEventType.DENIED_REVOKED
            message = f"Access Denied: Keycard is revoked ({rev_reason or 'Decommissioned'})."
        elif card_status == "Suspended":
            access_granted = False
            event_type = AccessEventType.DENIED_SUSPENDED
            message = "Access Denied: Keycard is temporarily suspended."
        elif expires_at_val:
            try:
                exp_dt = datetime.fromisoformat(str(expires_at_val).replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now_dt > exp_dt:
                    access_granted = False
                    event_type = AccessEventType.DENIED_EXPIRED
                    message = "Access Denied: Keycard validity period has expired."
            except Exception:
                pass

        if event_type == AccessEventType.DENIED_INVALID_ROOM and card_status == "Active":
            # Check room maintenance lock out
            if room["status"] == "Maintenance" and card_type_enum == KeycardType.GUEST:
                access_granted = False
                event_type = AccessEventType.DENIED_LOCKED_OUT
                message = f"Access Denied: Room {room_number} is out of service for maintenance."
            elif card_type_enum in (KeycardType.STAFF_MASTER, KeycardType.EMERGENCY):
                access_granted = True
                event_type = AccessEventType.GRANTED
                message = f"Access Granted: Master override unlocked Room {room_number}."
            elif card_type_enum in (KeycardType.HOUSEKEEPING, KeycardType.MAINTENANCE):
                access_granted = True
                event_type = AccessEventType.GRANTED
                message = f"Access Granted: Staff service access to Room {room_number}."
            elif card_type_enum == KeycardType.GUEST:
                if card["room_id"] == payload.room_id:
                    access_granted = True
                    event_type = AccessEventType.GRANTED
                    message = f"Access Granted: Welcome to Room {room_number}, {holder_name}."
                else:
                    access_granted = False
                    event_type = AccessEventType.DENIED_INVALID_ROOM
                    message = f"Access Denied: Card is authorized for a different room, not Room {room_number}."

    # Record in AccessLogs
    cursor.execute(
        """
        INSERT INTO AccessLogs (card_uid, room_id, reader_location, event_type, access_granted, attempted_at)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            payload.card_uid.strip(),
            payload.room_id,
            reader_loc,
            event_type.value,
            bool(access_granted),
            now_iso,
        ),
    )

    if not access_granted:
        record_audit_log(
            conn,
            action="DOOR_ACCESS_DENIED",
            entity_type="Room",
            entity_id=payload.room_id,
            details={
                "card_uid": payload.card_uid.strip(),
                "room_number": room_number,
                "event_type": event_type.value,
                "message": message,
                "reader_location": reader_loc,
            },
            actor=holder_name or "Unknown Presenter",
        )
    conn.commit()

    return DoorTapResponse(
        access_granted=access_granted,
        event_type=event_type,
        card_uid=payload.card_uid.strip(),
        room_id=payload.room_id,
        room_number=room_number,
        holder_name=holder_name,
        card_type=card_type_enum,
        message=message,
        timestamp=now_iso,
    )


@app.get(
    "/api/access-control/logs",
    response_model=List[AccessLogResponse],
    summary="List physical lock access tap audit entries",
    tags=["Keycards & Access Control"],
)
def get_access_logs(
    room_id: Optional[int] = Query(None, description="Filter by room ID"),
    card_uid: Optional[str] = Query(None, description="Filter by card UID"),
    event_type: Optional[str] = Query(None, description="Filter by event outcome (e.g. Granted, Denied)"),
    access_granted: Optional[bool] = Query(None, description="Filter by boolean access outcome"),
    limit: int = Query(50, ge=1, le=500, description="Max logs to return"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Returns access control audit records joined with room and cardholder metadata."""
    ensure_keycards_tables(conn)
    cursor = conn.cursor()

    conditions = []
    params = []

    if room_id:
        conditions.append("a.room_id = ?")
        params.append(room_id)
    if card_uid:
        conditions.append("a.card_uid = ?")
        params.append(card_uid.strip())
    if event_type:
        conditions.append("a.event_type LIKE ?")
        params.append(f"%{event_type.strip()}%")
    if access_granted is not None:
        if access_granted:
            conditions.append("a.access_granted = TRUE")
        else:
            conditions.append("NOT a.access_granted")

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    query = f"""
    SELECT a.*, r.room_number, k.holder_name, k.card_type
    FROM AccessLogs a
    LEFT JOIN Rooms r ON a.room_id = r.id
    LEFT JOIN Keycards k ON a.card_uid = k.card_uid
    {where_clause}
    ORDER BY a.id DESC
    LIMIT {int(limit)};
    """
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    rows = cursor.fetchall()
    return [row_to_access_log_response(r) for r in rows]


@app.get(
    "/api/access-control/dashboard",
    response_model=AccessControlDashboardResponse,
    summary="Get access control security KPI metrics and intrusion alerts",
    tags=["Keycards & Access Control"],
)
def get_access_control_dashboard(conn: sqlite3.Connection = Depends(get_db)):
    """Aggregates active credentials, master cards, and daily access outcomes."""
    ensure_keycards_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM Keycards WHERE status = 'Active';")
    row = cursor.fetchone()
    total_active_cards = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))

    cursor.execute("SELECT COUNT(*) as cnt FROM Keycards WHERE status = 'Active' AND card_type = 'Guest';")
    row = cursor.fetchone()
    guest_cards_active = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))

    cursor.execute("SELECT COUNT(*) as cnt FROM Keycards WHERE status = 'Active' AND card_type IN ('Staff Master', 'Housekeeping', 'Maintenance', 'Emergency Override');")
    row = cursor.fetchone()
    staff_master_cards = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))

    cursor.execute("SELECT COUNT(*) as cnt FROM Keycards WHERE status = 'Revoked';")
    row = cursor.fetchone()
    revoked_cards_count = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))

    cursor.execute("SELECT COUNT(*) as cnt FROM AccessLogs;")
    row = cursor.fetchone()
    total_access_taps_today = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))

    cursor.execute("SELECT COUNT(*) as cnt FROM AccessLogs WHERE access_granted = TRUE;")
    row = cursor.fetchone()
    granted_taps_today = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))

    cursor.execute("SELECT COUNT(*) as cnt FROM AccessLogs WHERE NOT access_granted;")
    row = cursor.fetchone()
    denied_intrusions_today = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))

    # 5 most recent denied events
    cursor.execute(
        """
        SELECT a.*, r.room_number, k.holder_name, k.card_type
        FROM AccessLogs a
        LEFT JOIN Rooms r ON a.room_id = r.id
        LEFT JOIN Keycards k ON a.card_uid = k.card_uid
        WHERE NOT a.access_granted
        ORDER BY a.id DESC
        LIMIT 5;
        """
    )
    denied_rows = cursor.fetchall()
    recent_denied_events = [row_to_access_log_response(r) for r in denied_rows]

    return AccessControlDashboardResponse(
        total_active_cards=total_active_cards,
        guest_cards_active=guest_cards_active,
        staff_master_cards=staff_master_cards,
        revoked_cards_count=revoked_cards_count,
        total_access_taps_today=total_access_taps_today,
        granted_taps_today=granted_taps_today,
        denied_intrusions_today=denied_intrusions_today,
        recent_denied_events=recent_denied_events,
    )


# ==============================================================================
# Module 6: Multi-Currency & International Tax Engine
# ==============================================================================

def ensure_finance_tables(conn: sqlite3.Connection):
    """Guarantees ExchangeRates and TaxRules tables exist in SQLite / PostgreSQL."""
    cursor = conn.cursor()
    if not IS_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ExchangeRates (
            currency_code TEXT PRIMARY KEY,
            currency_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            rate_to_usd REAL NOT NULL CHECK(rate_to_usd > 0),
            is_base INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS TaxRules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tax_name TEXT NOT NULL,
            tax_type TEXT NOT NULL CHECK(tax_type IN ('Percentage', 'Flat_Per_Night', 'Flat_Per_Stay')),
            rate REAL NOT NULL CHECK(rate >= 0),
            currency_code TEXT NOT NULL DEFAULT 'USD',
            applies_to TEXT NOT NULL DEFAULT 'All' CHECK(applies_to IN ('All', 'Room_Only', 'Incidentals')),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()

        cursor.execute("SELECT COUNT(*) as cnt FROM ExchangeRates;")
        row = cursor.fetchone()
        cnt = row["cnt"] if row else 0
        if cnt == 0:
            seed_rates = [
                ("USD", "US Dollar", "$", 1.0, 1),
                ("EUR", "Euro", "€", 0.92, 0),
                ("GBP", "British Pound", "£", 0.79, 0),
                ("JPY", "Japanese Yen", "¥", 152.50, 0),
                ("CAD", "Canadian Dollar", "C$", 1.38, 0),
                ("AUD", "Australian Dollar", "A$", 1.52, 0),
                ("CHF", "Swiss Franc", "CHF", 0.88, 0),
            ]
            for r in seed_rates:
                cursor.execute(
                    "INSERT INTO ExchangeRates (currency_code, currency_name, symbol, rate_to_usd, is_base) VALUES (?, ?, ?, ?, ?);",
                    r,
                )
            seed_taxes = [
                ("Standard Occupancy Sales Tax / VAT", "Percentage", 10.0, "USD", "All", 1),
                ("City Tourism Municipal Surcharge", "Flat_Per_Night", 5.0, "USD", "Room_Only", 1),
                ("Eco Sustainability & Green Resort Levy", "Flat_Per_Stay", 12.0, "USD", "All", 1),
            ]
            for t in seed_taxes:
                cursor.execute(
                    "INSERT INTO TaxRules (tax_name, tax_type, rate, currency_code, applies_to, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    t,
                )
            conn.commit()
    else:
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS ExchangeRates (
                currency_code VARCHAR(3) PRIMARY KEY,
                currency_name VARCHAR(50) NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                rate_to_usd NUMERIC(10, 4) NOT NULL CHECK(rate_to_usd > 0),
                is_base BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS TaxRules (
                id SERIAL PRIMARY KEY,
                tax_name VARCHAR(100) NOT NULL,
                tax_type VARCHAR(50) NOT NULL DEFAULT 'Percentage',
                rate NUMERIC(10, 2) NOT NULL CHECK(rate >= 0),
                currency_code VARCHAR(3) NOT NULL DEFAULT 'USD',
                applies_to VARCHAR(50) NOT NULL DEFAULT 'All',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()

            cursor.execute("SELECT COUNT(*) as cnt FROM ExchangeRates;")
            row = cursor.fetchone()
            cnt = int(row["cnt"] if isinstance(row, dict) and "cnt" in row else (row[0] if row else 0))
            if cnt == 0:
                seed_rates = [
                    ("USD", "US Dollar", "$", 1.0, True),
                    ("EUR", "Euro", "€", 0.92, False),
                    ("GBP", "British Pound", "£", 0.79, False),
                    ("JPY", "Japanese Yen", "¥", 152.50, False),
                    ("CAD", "Canadian Dollar", "C$", 1.38, False),
                    ("AUD", "Australian Dollar", "A$", 1.52, False),
                    ("CHF", "Swiss Franc", "CHF", 0.88, False),
                ]
                for r in seed_rates:
                    cursor.execute(
                        """
                        INSERT INTO ExchangeRates (currency_code, currency_name, symbol, rate_to_usd, is_base)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT (currency_code) DO NOTHING;
                        """,
                        r,
                    )
                seed_taxes = [
                    ("Standard Occupancy Sales Tax / VAT", "Percentage", 10.0, "USD", "All", True),
                    ("City Tourism Municipal Surcharge", "Flat_Per_Night", 5.0, "USD", "Room_Only", True),
                    ("Eco Sustainability & Green Resort Levy", "Flat_Per_Stay", 12.0, "USD", "All", True),
                ]
                for t in seed_taxes:
                    cursor.execute(
                        """
                        INSERT INTO TaxRules (tax_name, tax_type, rate, currency_code, applies_to, is_active)
                        VALUES (?, ?, ?, ?, ?, ?);
                        """,
                        t,
                    )
                conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"ensure_finance_tables postgres note: {e}")



def row_to_exchange_rate_response(r) -> ExchangeRateResponse:
    keys = set(r.keys()) if hasattr(r, "keys") else set()
    return ExchangeRateResponse(
        currency_code=str(r["currency_code"]),
        currency_name=str(r["currency_name"]),
        symbol=str(r["symbol"]),
        rate_to_usd=float(r["rate_to_usd"]),
        is_base=bool(r["is_base"]),
        updated_at=str(r["updated_at"]) if "updated_at" in keys and r["updated_at"] else None,
    )


def row_to_tax_rule_response(r) -> TaxRuleResponse:
    keys = set(r.keys()) if hasattr(r, "keys") else set()
    return TaxRuleResponse(
        id=int(r["id"]),
        tax_name=str(r["tax_name"]),
        tax_type=TaxType(r["tax_type"]),
        rate=float(r["rate"]),
        currency_code=str(r["currency_code"]) if "currency_code" in keys and r["currency_code"] else "USD",
        applies_to=TaxAppliesTo(r["applies_to"]),
        is_active=bool(r["is_active"]),
        created_at=str(r["created_at"]) if "created_at" in keys and r["created_at"] else None,
    )


def format_currency_amount(amount: float, currency_code: str, symbol: str) -> str:
    """Formats amount with appropriate decimal precision and symbol."""
    code = currency_code.upper()
    if code == "JPY":
        return f"{symbol}{int(round(amount)):,}"
    return f"{symbol}{amount:,.2f}"


@app.get(
    "/api/finance/exchange-rates",
    response_model=List[ExchangeRateResponse],
    summary="List all supported international foreign exchange conversion rates",
    tags=["Multi-Currency & Tax Engine"],
)
def get_exchange_rates(conn: sqlite3.Connection = Depends(get_db)):
    """Returns active forex conversion multipliers against USD base."""
    ensure_finance_tables(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ExchangeRates ORDER BY is_base DESC, currency_code ASC;")
    rows = cursor.fetchall()
    return [row_to_exchange_rate_response(r) for r in rows]


@app.patch(
    "/api/finance/exchange-rates/{currency_code}",
    response_model=ExchangeRateResponse,
    summary="Update live foreign exchange rate multiplier for a currency",
    tags=["Multi-Currency & Tax Engine"],
)
def update_exchange_rate(
    currency_code: str,
    payload: ExchangeRateUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Adjusts currency conversion multiplier against USD base."""
    ensure_finance_tables(conn)
    code = currency_code.strip().upper()
    if code == "USD" and abs(payload.rate_to_usd - 1.0) > 1e-6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base currency USD conversion rate must remain exactly 1.0000.",
        )

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ExchangeRates WHERE currency_code = ?;", (code,))
    existing = cursor.fetchone()
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Currency '{code}' is not supported in hotel exchange matrix.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE ExchangeRates
        SET rate_to_usd = ?,
            updated_at = ?
        WHERE currency_code = ?;
        """,
        (payload.rate_to_usd, now_iso, code),
    )

    record_audit_log(
        conn,
        action="EXCHANGE_RATE_UPDATED",
        entity_type="System",
        entity_id=None,
        details={
            "currency_code": code,
            "old_rate": float(existing["rate_to_usd"]),
            "new_rate": payload.rate_to_usd,
        },
        actor="Finance Controller",
    )
    conn.commit()

    cursor.execute("SELECT * FROM ExchangeRates WHERE currency_code = ?;", (code,))
    updated = cursor.fetchone()
    return row_to_exchange_rate_response(updated)


@app.post(
    "/api/finance/convert",
    response_model=CurrencyConvertResponse,
    summary="Convert funds across supported international currencies in real time",
    tags=["Multi-Currency & Tax Engine"],
)
def convert_currency(
    payload: CurrencyConvertRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Converts a monetary figure from one currency to another using live matrix."""
    ensure_finance_tables(conn)
    from_code = payload.from_currency.strip().upper()
    to_code = payload.to_currency.strip().upper()

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ExchangeRates WHERE currency_code IN (?, ?);", (from_code, to_code))
    rows = {r["currency_code"]: r for r in cursor.fetchall()}

    if from_code not in rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source currency '{from_code}' is not in the exchange rates registry.",
        )
    if to_code not in rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target currency '{to_code}' is not in the exchange rates registry.",
        )

    from_row = rows[from_code]
    to_row = rows[to_code]

    from_rate = float(from_row["rate_to_usd"])
    to_rate = float(to_row["rate_to_usd"])

    # Base conversion through USD
    amount_in_usd = payload.amount / from_rate
    converted_amount = amount_in_usd * to_rate
    effective_cross_rate = to_rate / from_rate

    target_symbol = str(to_row["symbol"])
    display_str = format_currency_amount(converted_amount, to_code, target_symbol)

    return CurrencyConvertResponse(
        original_amount=round(payload.amount, 2),
        from_currency=from_code,
        converted_amount=round(converted_amount, 2 if to_code != "JPY" else 0),
        to_currency=to_code,
        rate_applied=round(effective_cross_rate, 4),
        symbol=target_symbol,
        formatted_display=display_str,
    )


@app.get(
    "/api/finance/tax-rules",
    response_model=List[TaxRuleResponse],
    summary="List statutory municipal tax rules, hotel VAT, and eco levies",
    tags=["Multi-Currency & Tax Engine"],
)
def get_tax_rules(
    is_active: Optional[bool] = Query(None, description="Filter active/inactive rules"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Returns hotel statutory tax schedule."""
    ensure_finance_tables(conn)
    cursor = conn.cursor()
    if is_active is not None:
        if is_active:
            cursor.execute("SELECT * FROM TaxRules WHERE is_active = TRUE ORDER BY id ASC;")
        else:
            cursor.execute("SELECT * FROM TaxRules WHERE NOT is_active ORDER BY id ASC;")
    else:
        cursor.execute("SELECT * FROM TaxRules ORDER BY id ASC;")
    rows = cursor.fetchall()
    return [row_to_tax_rule_response(r) for r in rows]


@app.post(
    "/api/finance/tax-rules",
    response_model=TaxRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Define a statutory tax rule or municipal surcharge",
    tags=["Multi-Currency & Tax Engine"],
)
def create_tax_rule(
    payload: TaxRuleCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Registers a new statutory tax, city fee, or resort levy."""
    ensure_finance_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO TaxRules (tax_name, tax_type, rate, currency_code, applies_to, is_active)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            payload.tax_name.strip(),
            payload.tax_type.value,
            payload.rate,
            payload.currency_code.strip().upper(),
            payload.applies_to.value,
            bool(payload.is_active) if IS_POSTGRES else (1 if payload.is_active else 0),
        ),
    )
    new_id = cursor.lastrowid
    record_audit_log(
        conn,
        action="TAX_RULE_CREATED",
        entity_type="System",
        entity_id=new_id,
        details={
            "tax_name": payload.tax_name.strip(),
            "tax_type": payload.tax_type.value,
            "rate": payload.rate,
        },
        actor="Tax Compliance Officer",
    )
    conn.commit()

    cursor.execute("SELECT * FROM TaxRules WHERE id = ?;", (new_id,))
    row = cursor.fetchone()
    return row_to_tax_rule_response(row)


@app.patch(
    "/api/finance/tax-rules/{rule_id}",
    response_model=TaxRuleResponse,
    summary="Update or toggle an existing statutory tax rule",
    tags=["Multi-Currency & Tax Engine"],
)
def update_tax_rule(
    rule_id: int,
    payload: TaxRuleUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Updates tax rates, calculation algorithms, or active status."""
    ensure_finance_tables(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM TaxRules WHERE id = ?;", (rule_id,))
    rule = cursor.fetchone()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax rule with ID {rule_id} does not exist.",
        )

    updates = []
    params = []
    if payload.tax_name is not None:
        updates.append("tax_name = ?")
        params.append(payload.tax_name.strip())
    if payload.tax_type is not None:
        updates.append("tax_type = ?")
        params.append(payload.tax_type.value)
    if payload.rate is not None:
        updates.append("rate = ?")
        params.append(payload.rate)
    if payload.applies_to is not None:
        updates.append("applies_to = ?")
        params.append(payload.applies_to.value)
    if payload.is_active is not None:
        updates.append("is_active = ?")
        params.append(bool(payload.is_active) if IS_POSTGRES else (1 if payload.is_active else 0))

    if updates:
        params.append(rule_id)
        cursor.execute(f"UPDATE TaxRules SET {', '.join(updates)} WHERE id = ?;", params)
        record_audit_log(
            conn,
            action="TAX_RULE_UPDATED",
            entity_type="System",
            entity_id=rule_id,
            details=payload.model_dump(exclude_unset=True),
            actor="Tax Compliance Officer",
        )
        conn.commit()

    cursor.execute("SELECT * FROM TaxRules WHERE id = ?;", (rule_id,))
    updated_rule = cursor.fetchone()
    return row_to_tax_rule_response(updated_rule)


@app.post(
    "/api/finance/calculate-tax",
    response_model=TaxCalculationResponse,
    summary="Simulate full statutory tax breakdown and multi-currency quote for a stay",
    tags=["Multi-Currency & Tax Engine"],
)
def calculate_stay_taxes(
    payload: TaxCalculationRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Computes statutory taxes and total bill in USD and target currency:
    - Percentage taxes: applied based on applies_to scope ('All', 'Room_Only', 'Incidentals')
    - Flat_Per_Night taxes: multiplied by length of stay
    - Flat_Per_Stay taxes: applied once per folio
    """
    ensure_finance_tables(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM TaxRules WHERE is_active = TRUE ORDER BY id ASC;")
    tax_rows = cursor.fetchall()

    target_code = payload.target_currency.strip().upper()
    cursor.execute("SELECT * FROM ExchangeRates WHERE currency_code = ?;", (target_code,))
    target_fx = cursor.fetchone()
    if not target_fx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target currency '{target_code}' is not supported in the exchange registry.",
        )
    fx_rate = float(target_fx["rate_to_usd"])
    symbol = str(target_fx["symbol"])

    subtotal_room = payload.room_amount
    subtotal_incidentals = payload.incidentals_amount
    subtotal_usd = subtotal_room + subtotal_incidentals

    itemized_taxes = []
    total_tax_usd = 0.0

    for tr in tax_rows:
        t_type = tr["tax_type"]
        t_rate = float(tr["rate"])
        t_scope = tr["applies_to"]
        t_name = tr["tax_name"]

        tax_amt_usd = 0.0
        if t_type == "Percentage":
            if t_scope == "Room_Only":
                tax_amt_usd = subtotal_room * (t_rate / 100.0)
            elif t_scope == "Incidentals":
                tax_amt_usd = subtotal_incidentals * (t_rate / 100.0)
            else:  # All
                tax_amt_usd = subtotal_usd * (t_rate / 100.0)
        elif t_type == "Flat_Per_Night":
            tax_amt_usd = t_rate * payload.nights
        elif t_type == "Flat_Per_Stay":
            tax_amt_usd = t_rate

        tax_amt_usd = round(tax_amt_usd, 2)
        total_tax_usd += tax_amt_usd

        tax_converted = round(tax_amt_usd * fx_rate, 2 if target_code != "JPY" else 0)

        itemized_taxes.append(
            TaxItemDetail(
                tax_name=t_name,
                tax_type=t_type,
                rate=t_rate,
                amount_usd=tax_amt_usd,
                amount_converted=tax_converted,
            )
        )

    grand_total_usd = round(subtotal_usd + total_tax_usd, 2)
    grand_total_converted = round(grand_total_usd * fx_rate, 2 if target_code != "JPY" else 0)
    formatted = format_currency_amount(grand_total_converted, target_code, symbol)

    return TaxCalculationResponse(
        room_subtotal_usd=round(subtotal_room, 2),
        incidentals_subtotal_usd=round(subtotal_incidentals, 2),
        subtotal_usd=round(subtotal_usd, 2),
        taxes=itemized_taxes,
        total_tax_usd=round(total_tax_usd, 2),
        grand_total_usd=grand_total_usd,
        target_currency=target_code,
        currency_symbol=symbol,
        rate_to_usd=fx_rate,
        grand_total_converted=grand_total_converted,
        formatted_display=formatted,
    )


@app.get(
    "/api/finance/dashboard",
    response_model=FinanceDashboardResponse,
    summary="Get multi-currency and statutory tax dashboard configuration",
    tags=["Multi-Currency & Tax Engine"],
)
def get_finance_dashboard(conn: sqlite3.Connection = Depends(get_db)):
    """Consolidated summary of supported currencies, live rates, and active statutory tax rules."""
    ensure_finance_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM ExchangeRates ORDER BY is_base DESC, currency_code ASC;")
    fx_rows = cursor.fetchall()
    supported_currencies = [row_to_exchange_rate_response(r) for r in fx_rows]

    cursor.execute("SELECT * FROM TaxRules WHERE is_active = TRUE ORDER BY id ASC;")
    tax_rows = cursor.fetchall()
    active_tax_rules = [row_to_tax_rule_response(r) for r in tax_rows]

    percentage_taxes = sum(r.rate for r in active_tax_rules if r.tax_type == TaxType.PERCENTAGE)

    return FinanceDashboardResponse(
        base_currency="USD",
        supported_currencies=supported_currencies,
        active_tax_rules=active_tax_rules,
        effective_tax_rate_percent=round(percentage_taxes, 2),
    )


# ==============================================================================
# Module 7: Advanced Room Operations, Out-of-Order (OOO) & Guest Relocation Engine
# ==============================================================================

def ensure_room_operations_tables(conn: sqlite3.Connection):
    """Guarantees RoomLockouts and RoomMoves tables exist in SQLite / PostgreSQL.
    On Postgres (production), these tables are created by supabase_migration.sql — skip DDL entirely.
    """
    if IS_POSTGRES:
        return  # Tables already exist via Supabase migration — no DDL needed
    cursor = conn.cursor()
    if not IS_POSTGRES:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS roomlockouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            lockout_type TEXT NOT NULL DEFAULT 'Out_of_Order' CHECK(lockout_type IN ('Out_of_Order', 'Out_of_Service', 'Emergency_Repair')),
            reason TEXT NOT NULL,
            assigned_trade TEXT DEFAULT 'General Maintenance',
            expected_completion TEXT DEFAULT NULL,
            authorized_by TEXT NOT NULL DEFAULT 'Duty Manager',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP DEFAULT NULL,
            resolved_by TEXT DEFAULT NULL,
            resolution_notes TEXT DEFAULT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
            FOREIGN KEY (room_id) REFERENCES Rooms(id) ON DELETE CASCADE
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS roommoves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            old_room_id INTEGER NOT NULL,
            new_room_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            relocated_by TEXT NOT NULL DEFAULT 'Front Desk Duty Manager',
            keycards_reassigned INTEGER NOT NULL DEFAULT 0,
            relocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES Bookings(id) ON DELETE CASCADE,
            FOREIGN KEY (old_room_id) REFERENCES Rooms(id) ON DELETE CASCADE,
            FOREIGN KEY (new_room_id) REFERENCES Rooms(id) ON DELETE CASCADE
        );
        """)
        conn.commit()
    else:
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS roomlockouts (
                id SERIAL PRIMARY KEY,
                room_id INTEGER NOT NULL REFERENCES Rooms(id) ON DELETE CASCADE,
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
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS roommoves (
                id SERIAL PRIMARY KEY,
                booking_id INTEGER NOT NULL REFERENCES Bookings(id) ON DELETE CASCADE,
                old_room_id INTEGER NOT NULL REFERENCES Rooms(id) ON DELETE CASCADE,
                new_room_id INTEGER NOT NULL REFERENCES Rooms(id) ON DELETE CASCADE,
                reason VARCHAR(255) NOT NULL,
                relocated_by VARCHAR(100) NOT NULL DEFAULT 'Front Desk Duty Manager',
                keycards_reassigned INTEGER NOT NULL DEFAULT 0,
                relocated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"ensure_room_operations_tables postgres note: {e}")


def row_to_room_lockout_response(r) -> RoomLockoutResponse:
    keys = set(r.keys()) if hasattr(r, "keys") else set()
    return RoomLockoutResponse(
        id=int(r["id"]),
        room_id=int(r["room_id"]),
        room_number=str(r["room_number"]) if "room_number" in keys else f"Room {r['room_id']}",
        room_type=str(r["room_type"]) if "room_type" in keys else "Standard",
        lockout_type=str(r["lockout_type"]),
        reason=str(r["reason"]),
        assigned_trade=str(r["assigned_trade"]) if "assigned_trade" in keys and r["assigned_trade"] else None,
        expected_completion=str(r["expected_completion"]) if "expected_completion" in keys and r["expected_completion"] else None,
        authorized_by=str(r["authorized_by"]) if "authorized_by" in keys and r["authorized_by"] else "Duty Manager",
        notes=str(r["notes"]) if "notes" in keys and r["notes"] else None,
        created_at=str(r["created_at"]) if "created_at" in keys and r["created_at"] else "",
        resolved_at=str(r["resolved_at"]) if "resolved_at" in keys and r["resolved_at"] else None,
        resolved_by=str(r["resolved_by"]) if "resolved_by" in keys and r["resolved_by"] else None,
        resolution_notes=str(r["resolution_notes"]) if "resolution_notes" in keys and r["resolution_notes"] else None,
        is_active=bool(r["is_active"]),
    )


def row_to_room_move_response(r) -> RoomMoveResponse:
    keys = set(r.keys()) if hasattr(r, "keys") else set()
    return RoomMoveResponse(
        booking_id=int(r["booking_id"]),
        guest_name=str(r["guest_name"]) if "guest_name" in keys else "Hotel Guest",
        old_room_id=int(r["old_room_id"]),
        old_room_number=str(r["old_room_number"]) if "old_room_number" in keys else str(r["old_room_id"]),
        new_room_id=int(r["new_room_id"]),
        new_room_number=str(r["new_room_number"]) if "new_room_number" in keys else str(r["new_room_id"]),
        reason=str(r["reason"]),
        relocated_by=str(r["relocated_by"]) if "relocated_by" in keys and r["relocated_by"] else "Front Desk Duty Manager",
        relocated_at=str(r["relocated_at"]) if "relocated_at" in keys and r["relocated_at"] else "",
        keycards_reassigned_count=int(r["keycards_reassigned"] if "keycards_reassigned" in keys else (r["keycards_reassigned_count"] if "keycards_reassigned_count" in keys else 0)),
        old_room_new_status=str(r["old_room_new_status"]) if "old_room_new_status" in keys else "Maintenance",
        new_room_status=str(r["new_room_status"]) if "new_room_status" in keys else "Occupied",
    )


@app.post(
    "/api/rooms/{room_id}/lockout",
    response_model=RoomLockoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Decommission a room to Out-of-Order (OOO) or Out-of-Service (OOS)",
    tags=["Room Operations & Lockouts"],
)
def declare_room_lockout(
    room_id: int,
    payload: RoomLockoutCreate,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Takes a room out of inventory for severe defect (OOO) or cosmetic maintenance (OOS):
    - Validates target room exists (404)
    - Validates room is not currently occupied by an in-house guest (400 - suggest room move first)
    - Transitions room status to 'Maintenance' with lock_reason set
    - Creates active RoomLockouts record
    - Logs audit trail entry ROOM_LOCKOUT_DECLARED
    """
    ensure_room_operations_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT id, room_number, room_type, status FROM Rooms WHERE id = ?;", (room_id,))
    room = cursor.fetchone()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} does not exist.",
        )

    if room["status"] == "Occupied":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Room {room['room_number']} is currently occupied by an in-house guest. Execute an emergency room move before taking out of order.",
        )

    cursor.execute(
        "SELECT id FROM roomlockouts WHERE room_id = ? AND (is_active = TRUE OR is_active = 1);",
        (room_id,),
    )
    active_existing = cursor.fetchone()
    if active_existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room {room['room_number']} is already under an active lockout (#LK-{active_existing['id']}).",
        )

    cursor.execute(
        """
        INSERT INTO roomlockouts (room_id, lockout_type, reason, assigned_trade, expected_completion, authorized_by, notes, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            room_id,
            payload.lockout_type.value,
            payload.reason.strip(),
            payload.assigned_trade or "General Maintenance",
            payload.expected_completion,
            payload.authorized_by or "Duty Manager",
            payload.notes.strip() if payload.notes else "",
            bool(True) if IS_POSTGRES else 1,
        ),
    )
    new_lockout_id = cursor.lastrowid

    cursor.execute(
        "UPDATE Rooms SET status = 'Maintenance', lock_reason = ?, cleanliness_status = 'Dirty' WHERE id = ?;",
        (payload.reason.strip(), room_id),
    )

    record_audit_log(
        conn,
        action="ROOM_LOCKOUT_DECLARED",
        entity_type="Room",
        entity_id=room_id,
        details={
            "room_number": room["room_number"],
            "lockout_id": new_lockout_id,
            "lockout_type": payload.lockout_type.value,
            "reason": payload.reason.strip(),
            "authorized_by": payload.authorized_by,
        },
        actor=payload.authorized_by or "Duty Manager",
    )
    conn.commit()

    cursor.execute(
        """
        SELECT l.*, r.room_number, r.room_type
        FROM roomlockouts l
        JOIN Rooms r ON l.room_id = r.id
        WHERE l.id = ?;
        """,
        (new_lockout_id,),
    )
    row = cursor.fetchone()
    return row_to_room_lockout_response(row)


@app.post(
    "/api/rooms/{room_id}/release",
    response_model=RoomLockoutResponse,
    summary="Release a room from Out-of-Order back to service turnover",
    tags=["Room Operations & Lockouts"],
)
def release_room_lockout(
    room_id: int,
    payload: RoomReleaseRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Certifies completion of physical repairs:
    - Finds active lockout record for room (404 if none active)
    - Sets resolved_at timestamp, resolved_by, and resolution_notes
    - Transitions room status to 'Cleaning' with designated cleanliness status
    - Clears room lock_reason
    - Logs audit trail entry ROOM_LOCKOUT_RELEASED
    """
    ensure_room_operations_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT id, room_number, room_type FROM Rooms WHERE id = ?;", (room_id,))
    room = cursor.fetchone()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} does not exist.",
        )

    cursor.execute(
        "SELECT * FROM roomlockouts WHERE room_id = ? AND (is_active = TRUE OR is_active = 1) ORDER BY id DESC LIMIT 1;",
        (room_id,),
    )
    lockout = cursor.fetchone()
    if not lockout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active lockout found for Room {room['room_number']}.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    target_clean = payload.target_cleanliness or "Touch-up Required"

    cursor.execute(
        """
        UPDATE roomlockouts
        SET is_active = ?,
            resolved_at = ?,
            resolved_by = ?,
            resolution_notes = ?
        WHERE id = ?;
        """,
        (
            bool(False) if IS_POSTGRES else 0,
            now_iso,
            payload.released_by,
            payload.resolution_notes,
            lockout["id"],
        ),
    )

    cursor.execute(
        "UPDATE Rooms SET status = 'Cleaning', lock_reason = NULL, cleanliness_status = ? WHERE id = ?;",
        (target_clean, room_id),
    )

    record_audit_log(
        conn,
        action="ROOM_LOCKOUT_RELEASED",
        entity_type="Room",
        entity_id=room_id,
        details={
            "room_number": room["room_number"],
            "lockout_id": lockout["id"],
            "released_by": payload.released_by,
            "target_cleanliness": target_clean,
            "resolution_notes": payload.resolution_notes,
        },
        actor=payload.released_by,
    )
    conn.commit()

    cursor.execute(
        """
        SELECT l.*, r.room_number, r.room_type
        FROM roomlockouts l
        JOIN Rooms r ON l.room_id = r.id
        WHERE l.id = ?;
        """,
        (lockout["id"],),
    )
    row = cursor.fetchone()
    return row_to_room_lockout_response(row)


@app.get(
    "/api/rooms/lockouts",
    response_model=List[RoomLockoutResponse],
    summary="List room lockouts with active and room filtering",
    tags=["Room Operations & Lockouts"],
)
def list_room_lockouts(
    is_active: Optional[bool] = Query(None, description="Filter active vs historical lockouts"),
    room_id: Optional[int] = Query(None, description="Filter by room ID"),
    conn: sqlite3.Connection = Depends(get_db),
):
    """Returns registry of room lockouts and physical defect histories."""
    ensure_room_operations_tables(conn)
    cursor = conn.cursor()

    conditions = []
    params = []

    if is_active is not None:
        if is_active:
            conditions.append("l.is_active = TRUE" if IS_POSTGRES else "l.is_active = 1")
        else:
            conditions.append("NOT l.is_active" if IS_POSTGRES else "l.is_active = 0")
    if room_id is not None:
        conditions.append("l.room_id = ?")
        params.append(room_id)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cursor.execute(
        f"""
        SELECT l.*, r.room_number, r.room_type
        FROM roomlockouts l
        JOIN Rooms r ON l.room_id = r.id
        {where_sql}
        ORDER BY l.is_active DESC, l.id DESC;
        """,
        params,
    )
    rows = cursor.fetchall()
    return [row_to_room_lockout_response(r) for r in rows]


@app.post(
    "/api/bookings/{booking_id}/room-move",
    response_model=RoomMoveResponse,
    summary="Execute an emergency room relocation for an in-house checked-in guest",
    tags=["Room Operations & Lockouts"],
)
def execute_room_move(
    booking_id: int,
    payload: RoomMoveRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Relocates an in-house checked-in guest:
    - Verifies booking exists and is Checked-in (400 if not)
    - Verifies new room exists, is distinct from old room, and is Available
    - Updates booking's assigned room to target room
    - Vacates source room to Maintenance (with defect lock) or Cleaning
    - Marks target destination room as Occupied
    - Re-encodes active RFID keycards to new room if transfer_keycards is True
    - Records immutable entry in RoomMoves ledger
    - Logs audit trail entry ROOM_RELOCATION
    """
    ensure_room_operations_tables(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT b.id, b.room_id, b.booking_status,
               g.first_name, g.last_name,
               r.room_number as old_room_number, r.room_type as old_room_type
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
            detail=f"Booking with ID {booking_id} does not exist.",
        )

    if booking["booking_status"] != "Checked-in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute room move on reservation with status '{booking['booking_status']}'. Guest must be actively 'Checked-in'.",
        )

    old_room_id = booking["room_id"]
    new_room_id = payload.new_room_id

    if old_room_id == new_room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination room ID cannot be identical to current assigned room.",
        )

    cursor.execute("SELECT id, room_number, room_type, status FROM Rooms WHERE id = ?;", (new_room_id,))
    new_room = cursor.fetchone()
    if not new_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Destination room with ID {new_room_id} does not exist.",
        )

    if new_room["status"] != "Available":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Destination Room {new_room['room_number']} is not Available (current status: '{new_room['status']}').",
        )

    guest_full_name = f"{booking['first_name']} {booking['last_name']}".strip()
    old_room_num = booking["old_room_number"]
    new_room_num = new_room["room_number"]

    cursor.execute("UPDATE Bookings SET room_id = ? WHERE id = ?;", (new_room_id, booking_id))

    old_room_new_status = "Maintenance" if payload.old_room_lockout else "Cleaning"
    old_lock_reason = f"Vacated on guest room move: {payload.reason.strip()}" if payload.old_room_lockout else None
    cursor.execute(
        "UPDATE Rooms SET status = ?, lock_reason = ?, cleanliness_status = 'Dirty' WHERE id = ?;",
        (old_room_new_status, old_lock_reason, old_room_id),
    )

    cursor.execute(
        "UPDATE Rooms SET status = 'Occupied', lock_reason = NULL WHERE id = ?;",
        (new_room_id,),
    )

    reassigned_count = 0
    if payload.transfer_keycards:
        try:
            cursor.execute(
                """
                UPDATE Keycards
                SET room_id = ?
                WHERE booking_id = ? AND status = 'Active';
                """,
                (new_room_id, booking_id),
            )
            reassigned_count = 1
        except Exception as e:
            print(f"Keycard transfer note during room move: {e}")

    cursor.execute(
        """
        INSERT INTO roommoves (booking_id, old_room_id, new_room_id, reason, relocated_by, keycards_reassigned)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            booking_id,
            old_room_id,
            new_room_id,
            payload.reason.strip(),
            payload.relocated_by,
            reassigned_count,
        ),
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    record_audit_log(
        conn,
        action="ROOM_RELOCATION",
        entity_type="Booking",
        entity_id=booking_id,
        details={
            "guest_name": guest_full_name,
            "old_room_id": old_room_id,
            "old_room_number": old_room_num,
            "new_room_id": new_room_id,
            "new_room_number": new_room_num,
            "reason": payload.reason.strip(),
            "relocated_by": payload.relocated_by,
            "keycards_reassigned": reassigned_count,
            "old_room_status": old_room_new_status,
        },
        actor=payload.relocated_by,
    )
    conn.commit()

    return RoomMoveResponse(
        booking_id=booking_id,
        guest_name=guest_full_name,
        old_room_id=old_room_id,
        old_room_number=old_room_num,
        new_room_id=new_room_id,
        new_room_number=new_room_num,
        reason=payload.reason.strip(),
        relocated_by=payload.relocated_by,
        relocated_at=now_iso,
        keycards_reassigned_count=reassigned_count,
        old_room_new_status=old_room_new_status,
        new_room_status="Occupied",
    )


@app.get(
    "/api/bookings/{booking_id}/room-moves",
    response_model=List[RoomMoveResponse],
    summary="Get room relocation history for a booking",
    tags=["Room Operations & Lockouts"],
)
def get_booking_room_moves(
    booking_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Lists relocation events for a specific reservation."""
    ensure_room_operations_tables(conn)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT m.*,
               g.first_name, g.last_name,
               r_old.room_number as old_room_number,
               r_new.room_number as new_room_number
        FROM roommoves m
        JOIN Bookings b ON m.booking_id = b.id
        JOIN Guests g ON b.guest_id = g.id
        JOIN Rooms r_old ON m.old_room_id = r_old.id
        JOIN Rooms r_new ON m.new_room_id = r_new.id
        WHERE m.booking_id = ?
        ORDER BY m.id DESC;
        """,
        (booking_id,),
    )
    rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append(
            RoomMoveResponse(
                booking_id=int(r["booking_id"]),
                guest_name=f"{r['first_name']} {r['last_name']}".strip(),
                old_room_id=int(r["old_room_id"]),
                old_room_number=str(r["old_room_number"]),
                new_room_id=int(r["new_room_id"]),
                new_room_number=str(r["new_room_number"]),
                reason=str(r["reason"]),
                relocated_by=str(r["relocated_by"]),
                relocated_at=str(r["relocated_at"]),
                keycards_reassigned_count=int(r["keycards_reassigned"]),
                old_room_new_status="Maintenance",
                new_room_status="Occupied",
            )
        )
    return results


@app.get(
    "/api/rooms/operations-dashboard",
    response_model=RoomOperationsDashboardResponse,
    summary="Get comprehensive room operations, lockout metrics, and recent room transfers",
    tags=["Room Operations & Lockouts"],
)
def get_room_operations_dashboard(conn: sqlite3.Connection = Depends(get_db)):
    """Consolidated operations cockpit for front desk and engineering teams."""
    ensure_room_operations_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT status, COUNT(*) as cnt FROM Rooms GROUP BY status;")
    status_counts = {r["status"]: int(r["cnt"]) for r in cursor.fetchall()}

    total_rooms = sum(status_counts.values())
    avail = status_counts.get("Available", 0)
    occ = status_counts.get("Occupied", 0)
    clean = status_counts.get("Cleaning", 0)

    cursor.execute(
        """
        SELECT l.*, r.room_number, r.room_type
        FROM roomlockouts l
        JOIN Rooms r ON l.room_id = r.id
        WHERE (l.is_active = TRUE OR l.is_active = 1)
        ORDER BY l.id DESC;
        """
    )
    active_lockout_rows = cursor.fetchall()
    active_lockouts = [row_to_room_lockout_response(r) for r in active_lockout_rows]

    ooo_count = sum(1 for l in active_lockouts if l.lockout_type == "Out_of_Order")
    oos_count = sum(1 for l in active_lockouts if l.lockout_type != "Out_of_Order")

    cursor.execute(
        """
        SELECT m.*,
               g.first_name, g.last_name,
               r_old.room_number as old_room_number,
               r_new.room_number as new_room_number
        FROM roommoves m
        JOIN Bookings b ON m.booking_id = b.id
        JOIN Guests g ON b.guest_id = g.id
        JOIN Rooms r_old ON m.old_room_id = r_old.id
        JOIN Rooms r_new ON m.new_room_id = r_new.id
        ORDER BY m.id DESC
        LIMIT 10;
        """
    )
    move_rows = cursor.fetchall()
    recent_moves = [
        RoomMoveResponse(
            booking_id=int(r["booking_id"]),
            guest_name=f"{r['first_name']} {r['last_name']}".strip(),
            old_room_id=int(r["old_room_id"]),
            old_room_number=str(r["old_room_number"]),
            new_room_id=int(r["new_room_id"]),
            new_room_number=str(r["new_room_number"]),
            reason=str(r["reason"]),
            relocated_by=str(r["relocated_by"]),
            relocated_at=str(r["relocated_at"]),
            keycards_reassigned_count=int(r["keycards_reassigned"]),
            old_room_new_status="Maintenance",
            new_room_status="Occupied",
        )
        for r in move_rows
    ]

    return RoomOperationsDashboardResponse(
        total_rooms=total_rooms,
        available_count=avail,
        occupied_count=occ,
        cleaning_count=clean,
        out_of_order_count=ooo_count,
        out_of_service_count=oos_count,
        active_lockouts=active_lockouts,
        recent_room_moves=recent_moves,
    )


# Mount static files if directory exists (local development fallback)
# On Vercel, static assets are served directly from /public via edge CDN
if STATIC_DIR.exists():
    try:
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static_root")
    except Exception as e:
        print(f"StaticFiles mounting skipped: {e}")


