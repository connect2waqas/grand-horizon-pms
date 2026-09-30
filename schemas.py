"""
schemas.py - Pydantic Data Models & Validation
Hotel Management System MVP

This module provides data contracts and validation schemas for Guests, Rooms,
and Bookings. It strictly decouples input schemas (payloads submitted by clients,
without IDs) from output schemas (persisted resources returned by the API, with
assigned IDs, calculated totals, and timestamps).
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==========================================
# Enums for Domain Integrity
# ==========================================

class RoomType(str, Enum):
    """Permitted room categories matching the DB CHECK constraint."""
    SINGLE = "Single"
    DOUBLE = "Double"
    FAMILY_SUITE = "Family Suite"


class RoomStatus(str, Enum):
    """Operational status of a room matching the DB CHECK constraint."""
    AVAILABLE = "Available"
    OCCUPIED = "Occupied"
    MAINTENANCE = "Maintenance"
    CLEANING = "Cleaning"


class CleanlinessStatus(str, Enum):
    """Housekeeping inspection state of an accommodation."""
    CLEAN = "Clean"
    DIRTY = "Dirty"
    INSPECTED = "Inspected"
    TOUCH_UP_REQUIRED = "Touch-up Required"


class BookingStatus(str, Enum):
    """Lifecycle status of a reservation matching the DB CHECK constraint."""
    CONFIRMED = "Confirmed"
    CHECKED_IN = "Checked-in"
    CHECKED_OUT = "Checked-out"
    CANCELLED = "Cancelled"


class VIPTier(str, Enum):
    """Loyalty and CRM tier classification."""
    STANDARD = "Standard"
    SILVER = "Silver"
    GOLD = "Gold"
    PLATINUM = "Platinum"


# ==========================================
# Guest Schemas
# ==========================================

class GuestBase(BaseModel):
    """Common attributes for Guest entities."""
    first_name: str = Field(..., min_length=1, max_length=50, description="Guest first name")
    last_name: str = Field(..., min_length=1, max_length=50, description="Guest last name")
    email: str = Field(..., description="Unique email address for contact and lookup")
    phone: str = Field(..., min_length=7, max_length=20, description="Phone number")
    vip_tier: VIPTier = Field(default=VIPTier.STANDARD, description="Guest VIP loyalty tier")
    notes: Optional[str] = Field(default="", max_length=1000, description="Guest preferences, dietary needs, or VIP requests")


class GuestCreate(GuestBase):
    """Input schema for creating a new guest profile (ID is omitted, assigned by database)."""
    pass


class GuestUpdate(BaseModel):
    """Input schema for updating an existing guest profile, VIP tier, or preferences."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    vip_tier: Optional[VIPTier] = None
    notes: Optional[str] = Field(None, max_length=1000)


class GuestResponse(GuestBase):
    """Output schema for returning guest details including server-assigned identity."""
    id: int
    created_at: Optional[str | datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GuestCRMResponse(BaseModel):
    """CRM aggregate profile with lifetime analytics, stays history, and VIP status."""
    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    vip_tier: VIPTier
    notes: Optional[str] = ""
    total_bookings: int = 0
    completed_stays: int = 0
    active_stays: int = 0
    cancelled_bookings: int = 0
    lifetime_spent: float = 0.0
    average_spend_per_stay: float = 0.0
    last_stay_date: Optional[date] = None
    created_at: Optional[str | datetime] = None

    model_config = ConfigDict(from_attributes=True)



# ==========================================
# Room Schemas
# ==========================================

class RoomBase(BaseModel):
    """Common attributes for Room entities with realistic architectural specifications."""
    room_number: str = Field(..., min_length=1, max_length=10, description="Unique room identifier number")
    room_type: RoomType = Field(..., description="Room category")
    price_per_night: float = Field(..., gt=0.0, description="Nightly rate, strictly positive")
    status: RoomStatus = Field(default=RoomStatus.AVAILABLE, description="Current room operational status")
    floor: int = Field(default=1, ge=1, le=50, description="Building floor level")
    max_occupancy: int = Field(default=2, ge=1, le=10, description="Maximum permitted guest occupancy")
    bed_type: str = Field(default="1 King Bed", description="Bed arrangement specification")
    view_type: str = Field(default="City Skyline", description="Window / Balcony view outlook")
    sq_meters: int = Field(default=35, ge=15, le=500, description="Room area in square meters")
    is_smoking: bool = Field(default=False, description="Smoking policy")
    cleanliness_status: CleanlinessStatus = Field(default=CleanlinessStatus.INSPECTED, description="Housekeeping inspection status")
    lock_reason: Optional[str] = Field(default=None, description="Reason if locked or out of service")


class RoomCreate(RoomBase):
    """Input schema for adding a room to the catalog (ID is omitted, assigned by database)."""
    pass


class RoomResponse(RoomBase):
    """Output schema for returning room inventory with database ID, status, and metadata."""
    id: int
    created_at: Optional[str | datetime] = None
    booked_until: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RoomStatusUpdate(BaseModel):
    """Schema for mutating room operational status (Housekeeping & Maintenance)."""
    status: RoomStatus = Field(..., description="Target operational status")
    lock_reason: Optional[str] = Field(default=None, description="Operational lock explanation if out of service")


class RoomHousekeepingUpdate(BaseModel):
    """Schema for updating room cleanliness and inspection checklist."""
    cleanliness_status: CleanlinessStatus = Field(..., description="Target housekeeping state")
    inspected_by: Optional[str] = Field(default="Head Housekeeper", description="Inspector staff identifier")
    notes: Optional[str] = Field(default="", description="Housekeeping inspection remarks")


class RoomSpecificationResponse(RoomResponse):
    """Detailed architectural and housekeeping dossier for room management."""
    active_booking_id: Optional[int] = None
    last_cleaned_at: Optional[str] = None


# ==========================================
# Amenity Schemas
# ==========================================

class AmenityBase(BaseModel):
    """Common attributes for Amenity add-ons."""
    name: str = Field(..., min_length=1, max_length=100, description="Amenity name")
    price: float = Field(..., ge=0.0, description="Price charged for the amenity, non-negative")
    description: Optional[str] = Field(None, max_length=255, description="Brief description of the amenity")


class AmenityCreate(AmenityBase):
    """Input schema for adding new amenities to the catalog."""
    pass


class AmenityResponse(AmenityBase):
    """Output schema for amenities including database assigned ID."""
    id: int
    created_at: Optional[str | datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Booking Schemas
# ==========================================
# Reservation & Booking Schemas (Module 2 Deepening)
# ==========================================

class GuaranteeType(str, Enum):
    """Reservation guarantee policy classification."""
    GUARANTEED = "Guaranteed"
    NON_GUARANTEED = "Non-Guaranteed"
    DEPOSIT_REQUIRED = "Deposit Required"


class BookingBase(BaseModel):
    """Base reservation attributes and realistic guest stay specifications."""
    check_in_date: date = Field(..., description="Check-in date (YYYY-MM-DD)")
    check_out_date: date = Field(..., description="Check-out date (YYYY-MM-DD)")
    adults: int = Field(default=1, ge=1, le=10, description="Adult guest count (min 1)")
    children: int = Field(default=0, ge=0, le=10, description="Child guest count")
    estimated_arrival_time: Optional[str] = Field(default="15:00", description="Estimated arrival time (HH:MM format)")
    special_requests: Optional[str] = Field(default="", max_length=500, description="Guest preferences, floor requests, or accessibility needs")
    guarantee_type: GuaranteeType = Field(default=GuaranteeType.GUARANTEED, description="Reservation guarantee status")
    early_checkin_requested: bool = Field(default=False, description="Early check-in priority flag")
    late_checkout_requested: bool = Field(default=False, description="Late check-out request flag")
    rate_plan_code: str = Field(default="BAR", description="Associated rate plan code (e.g. BAR, NON_REF, BB_PACKAGE)")


class BookingCreate(BookingBase):
    """
    Input schema for reserving a room.
    
    Accepts:
      - Target room ID
      - Stay dates
      - Guest identity (either existing guest_id or new guest profile)
      - Guest headcount (adults, children)
      - Arrival timing and special requests
      - Optional list of selected amenity IDs
    
    Note: 'total_price' and 'id' are omitted here; they are securely calculated
    and assigned by the server backend to prevent price tampering.
    """
    room_id: int = Field(..., gt=0, description="ID of the room to book")
    guest_id: Optional[int] = Field(None, gt=0, description="ID of existing guest, if registered")
    guest: Optional[GuestCreate] = Field(None, description="New guest information if not yet registered")
    amenity_ids: list[int] = Field(default_factory=list, description="List of chosen add-on amenity IDs")
    coupon_code: Optional[str] = Field(None, max_length=30, description="Optional promotional coupon code")
    apply_dynamic_pricing: bool = Field(False, description="Whether to apply weekend surge, seasonal rates, and LOS discounts")

    @model_validator(mode="after")
    def validate_booking_contract(self) -> "BookingCreate":
        # 1. Temporal validation: checkout must follow checkin
        if self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be strictly after check_in_date")
        
        # 2. Guest identity validation: at least one identity channel must be supplied
        if self.guest_id is None and self.guest is None:
            raise ValueError("Either 'guest_id' or guest profile information ('guest') must be provided.")
        
        return self


class BookingResponse(BaseModel):
    """
    Output schema for confirmed reservations.
    
    Contains system-assigned IDs, server-computed total price, booking status,
    relational sub-objects (room, guest), applied discounts, and chosen amenities.
    """
    id: int
    guest_id: int
    room_id: int
    check_in_date: date
    check_out_date: date
    total_price: float
    booking_status: BookingStatus
    created_at: Optional[str | datetime] = None
    coupon_code: Optional[str] = None
    discount_amount: float = 0.0
    adults: int = 1
    children: int = 0
    estimated_arrival_time: Optional[str] = "15:00"
    special_requests: Optional[str] = ""
    guarantee_type: GuaranteeType = GuaranteeType.GUARANTEED
    early_checkin_requested: bool = False
    late_checkout_requested: bool = False
    rate_plan_code: str = "BAR"
    room: Optional[RoomResponse] = None
    guest: Optional[GuestResponse] = None
    amenities: list[AmenityResponse] = Field(default_factory=list, description="Attached add-on amenities")

    model_config = ConfigDict(from_attributes=True)


class AutoAssignRequest(BaseModel):
    """Request contract for intelligent room auto-assignment algorithm."""
    check_in_date: date = Field(..., description="Desired check-in date")
    check_out_date: date = Field(..., description="Desired check-out date")
    room_type: Optional[RoomType] = Field(None, description="Preferred room category")
    floor: Optional[int] = Field(None, ge=1, le=10, description="Preferred building floor level")
    adults: int = Field(default=1, ge=1, le=10, description="Number of adult guests")
    children: int = Field(default=0, ge=0, le=10, description="Number of child guests")
    prefer_inspected: bool = Field(default=True, description="Prioritize rooms with Inspected cleanliness state")

    @model_validator(mode="after")
    def validate_dates(self) -> "AutoAssignRequest":
        if self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be strictly after check_in_date")
        return self


class AutoAssignResponse(BaseModel):
    """Response contract returning the optimal room candidate and match explanation."""
    assigned_room: Optional[RoomResponse] = Field(None, description="Optimal recommended room for reservation")
    match_score: int = Field(..., description="Algorithmic match confidence score (0-100)")
    criteria_applied: list[str] = Field(default_factory=list, description="Applied prioritization heuristics")
    available_alternatives: list[RoomResponse] = Field(default_factory=list, description="Secondary available room candidates")


# ==========================================
# Analytics & KPI Schemas
# ==========================================

class KPIAnalyticsResponse(BaseModel):
    """
    Consolidated property performance metrics for executive reporting.
    Calculates operational inventory, occupancy ratios, Average Daily Rate (ADR),
    Revenue Per Available Room (RevPAR), and arrival turnover.
    """
    total_rooms: int = Field(..., description="Total room inventory in property")
    active_rooms: int = Field(..., description="Rooms available for sale (excludes Maintenance)")
    available_rooms: int = Field(..., description="Rooms currently vacant and ready")
    occupied_rooms: int = Field(..., description="Rooms currently occupied")
    cleaning_rooms: int = Field(..., description="Rooms undergoing housekeeping")
    maintenance_rooms: int = Field(..., description="Rooms taken out of service for repair")
    occupancy_rate: float = Field(..., description="Percentage of active rooms occupied (0.0 to 100.0)")
    occupancy_rate_display: str = Field(..., description="Formatted occupancy percentage string (e.g. '66.7%')")
    estimated_daily_revenue: float = Field(default=0.0, description="Estimated daily revenue (sum of rates for occupied rooms)")
    adr: float = Field(..., description="Average Daily Rate for occupied inventory")
    revpar: float = Field(..., description="Revenue Per Available Room")
    today_checkins: int = Field(..., description="Arrivals scheduled for today")
    today_checkouts: int = Field(..., description="Departures scheduled for today")
    total_revenue: float = Field(..., description="Lifetime total confirmed booking revenue")
    monthly_revenue: float = Field(..., description="Confirmed revenue for current month")

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Lifecycle & Checkout Schemas
# ==========================================

class InvoiceItem(BaseModel):
    """Line item in a checkout statement or folio."""
    description: str = Field(..., description="Service or room charge description")
    quantity: int = Field(1, description="Quantity or nights billed")
    unit_price: float = Field(..., description="Price per unit")
    total_amount: float = Field(..., description="Line total amount")


class BookingCheckoutResponse(BaseModel):
    """Output schema for completed guest checkout folios."""
    booking_id: int
    guest_name: str
    guest_email: str
    room_number: str
    room_type: RoomType
    nights: int
    check_in_date: date
    check_out_date: date
    base_room_charge: float
    amenities_charge: float
    incidentals_charge: float = 0.0
    tax_amount: float
    grand_total: float
    status: BookingStatus
    room_status_after_checkout: RoomStatus
    checkout_timestamp: str
    invoice_breakdown: list[InvoiceItem]

    model_config = ConfigDict(from_attributes=True)


class BookingCancelResponse(BaseModel):
    """Output schema for processed reservation cancellations with policy calculations."""
    booking_id: int
    guest_name: str
    room_number: str
    original_total: float
    refund_amount: float
    cancellation_fee: float
    status: BookingStatus
    message: str

    model_config = ConfigDict(from_attributes=True)


class GuestDetailResponse(GuestCRMResponse):
    """Detailed CRM profile including full chronological stay history and folios."""
    stay_history: list[BookingResponse] = []


# ==========================================
# Module 11: Dynamic Pricing & Coupon Schemas
# ==========================================

class DiscountType(str, Enum):
    """Supported discount mechanisms."""
    PERCENTAGE = "Percentage"
    FIXED_AMOUNT = "FixedAmount"


class CouponBase(BaseModel):
    """Base schema for promotional coupons."""
    code: str = Field(..., min_length=3, max_length=30, description="Unique promo voucher code (alphanumeric)")
    discount_type: DiscountType = Field(..., description="Discount type (Percentage or FixedAmount)")
    discount_value: float = Field(..., gt=0.0, description="Percentage (e.g. 10.0 for 10%) or dollar deduction (e.g. 25.0)")
    valid_from: date = Field(..., description="Promo eligibility start date")
    valid_until: date = Field(..., description="Promo expiration date")
    min_total: float = Field(0.0, ge=0.0, description="Minimum order subtotal before discount can trigger")
    max_uses: int = Field(100, gt=0, description="Maximum allowed redemptions property-wide")
    is_active: bool = Field(True, description="Whether coupon is currently redeemable")


class CouponCreate(CouponBase):
    """Input schema for creating a promotional coupon."""
    pass


class CouponResponse(CouponBase):
    """Output schema for persisted promotional coupons."""
    id: int
    used_count: int = 0
    created_at: Optional[str | datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CouponValidateRequest(BaseModel):
    """Input payload to check validity of a coupon code against an order total."""
    code: str = Field(..., min_length=1, max_length=30)
    total_amount: float = Field(0.0, ge=0.0)


class CouponValidateResponse(BaseModel):
    """Evaluation result for coupon redemption."""
    is_valid: bool
    code: str
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[float] = None
    discount_amount: float = 0.0
    message: str


# ==========================================
# Module 3: Rate Plans & Yield Management Schemas
# ==========================================

class CancellationPolicy(str, Enum):
    """Cancellation terms for a rate plan."""
    FLEXIBLE = "Flexible (24h free cancellation)"
    MODERATE = "Moderate (48h cancellation)"
    NON_REFUNDABLE = "Non-Refundable (100% deposit locked)"


class MealPlanType(str, Enum):
    """Meal package options bundled into rate plans."""
    ROOM_ONLY = "Room Only"
    CONTINENTAL_BREAKFAST = "Continental Breakfast Included"
    FULL_BOARD = "Full Board (All Meals)"


class DemandYieldTier(str, Enum):
    """Dynamic yield management demand classification."""
    LOW_DEMAND = "Low Demand (Discounted Stimulus)"
    NORMAL_DEMAND = "Standard Demand"
    HIGH_DEMAND = "High Demand Surge (+15%)"
    PEAK_COMPRESSION = "Peak Compression Surge (+30%)"


class RatePlanBase(BaseModel):
    """Core rate plan configuration contract."""
    code: str = Field(..., max_length=30, description="Unique code (e.g. BAR, NON_REF, BB_PACKAGE)")
    name: str = Field(..., max_length=100, description="Display name")
    description: Optional[str] = Field(default="", description="Package terms and guest benefits")
    rate_multiplier: float = Field(default=1.0, gt=0, le=3.0, description="Base rate multiplier")
    cancellation_policy: CancellationPolicy = Field(default=CancellationPolicy.FLEXIBLE)
    meal_plan: MealPlanType = Field(default=MealPlanType.ROOM_ONLY)
    min_los: int = Field(default=1, ge=1, description="Minimum length of stay in nights")
    is_active: bool = Field(default=True)


class RatePlanCreate(RatePlanBase):
    pass


class RatePlanResponse(RatePlanBase):
    id: int
    created_at: Optional[str | datetime] = None
    model_config = ConfigDict(from_attributes=True)


class NightlyRateDetail(BaseModel):
    """Breakdown of dynamic pricing per night of stay."""
    stay_date: date
    day_name: str
    base_rate: float
    is_weekend: bool
    weekend_surge: float = 0.0
    is_summer: bool
    summer_surge: float = 0.0
    demand_yield_surge: float = 0.0
    rate_plan_multiplier: float = 1.0
    effective_rate: float


class PriceQuoteRequest(BaseModel):
    """Input schema to compute a dynamic pricing quote with multipliers and discounts."""
    room_id: int = Field(..., gt=0)
    check_in_date: date
    check_out_date: date
    guest_id: Optional[int] = None
    rate_plan_code: Optional[str] = Field(default="BAR", description="Rate plan code")
    amenity_ids: list[int] = Field(default_factory=list)
    coupon_code: Optional[str] = None


class PriceQuoteResponse(BaseModel):
    """Detailed dynamic pricing quotation breakdown."""
    room_id: int
    room_number: str
    room_type: RoomType
    nights: int
    nightly_details: list[NightlyRateDetail]
    raw_room_total: float
    weekend_surge_total: float
    seasonal_surge_total: float
    occupancy_surge_total: float = 0.0
    rate_plan_adjustment: float = 0.0
    length_of_stay_discount: float
    vip_discount: float
    net_room_charge: float
    amenities_charge: float
    coupon_discount: float
    coupon_code: Optional[str] = None
    coupon_applied: bool = False
    rate_plan_code: str = "BAR"
    rate_plan_name: str = "Best Available Rate"
    cancellation_policy: str = "Flexible (24h free cancellation)"
    meal_plan: str = "Room Only"
    occupancy_rate: float = 0.0
    demand_tier: DemandYieldTier = DemandYieldTier.NORMAL_DEMAND
    min_los_met: bool = True
    min_los_required: int = 1
    subtotal: float
    tax_amount: float
    grand_total: float


# ==========================================
# Module 12: Enterprise Audit Trail Schemas
# ==========================================

class AuditLogResponse(BaseModel):
    """Output schema for immutable audit ledger events."""
    id: int
    timestamp: str | datetime
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    actor: str = "Front Desk Agent"
    details: Optional[str] = None
    created_at: Optional[str | datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Module 13: Maintenance Work Orders & Housekeeping Dispatch
# ==========================================

class MaintenanceCategory(str, Enum):
    """Classifications of property maintenance issues."""
    PLUMBING = "Plumbing"
    ELECTRICAL = "Electrical"
    HVAC = "HVAC"
    FURNITURE = "Furniture"
    SANITIZATION = "Sanitization"
    STRUCTURAL = "Structural"
    GENERAL = "General"


class MaintenancePriority(str, Enum):
    """Urgency level of maintenance requests."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"


class MaintenanceStatus(str, Enum):
    """Lifecycle status of maintenance tickets."""
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    CANCELLED = "Cancelled"


class MaintenanceTicketBase(BaseModel):
    """Base schema for hotel room maintenance work orders."""
    room_id: int = Field(..., gt=0, description="Target room requiring maintenance")
    issue_description: str = Field(..., min_length=5, max_length=500, description="Clear description of the operational defect")
    category: MaintenanceCategory = Field(default=MaintenanceCategory.GENERAL, description="Trade classification")
    priority: MaintenancePriority = Field(default=MaintenancePriority.MEDIUM, description="Urgency priority")
    assigned_staff: Optional[str] = Field("Facilities Team", max_length=100, description="Technician or team assigned")
    reported_by: Optional[str] = Field("Housekeeping", max_length=100, description="Staff reporting the issue")
    estimated_cost: float = Field(0.0, ge=0.0, description="Estimated or authorized repair cost")


class MaintenanceTicketCreate(MaintenanceTicketBase):
    """Input schema for creating/dispatching a new maintenance work order."""
    auto_lock_room: bool = Field(True, description="Automatically place target room into Maintenance status if Priority is High or Urgent")


class MaintenanceTicketUpdate(BaseModel):
    """Input schema for updating work order status or resolving repairs."""
    status: Optional[MaintenanceStatus] = None
    priority: Optional[MaintenancePriority] = None
    assigned_staff: Optional[str] = None
    estimated_cost: Optional[float] = Field(None, ge=0.0)
    resolution_notes: Optional[str] = None
    auto_release_room: bool = Field(True, description="Automatically transition room to Cleaning when ticket is Resolved")


class MaintenanceTicketResponse(MaintenanceTicketBase):
    """Output schema for maintenance work order records."""
    id: int
    status: MaintenanceStatus
    resolution_notes: str = ""
    created_at: Optional[str | datetime] = None
    resolved_at: Optional[str | datetime] = None
    room_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MaintenanceSummaryResponse(BaseModel):
    """Consolidated metrics for facilities and housekeeping dashboard."""
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    urgent_tickets: int

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Module 14: Guest Folio & Incidentals Billing Engine
# ==========================================

class FolioCategory(str, Enum):
    """Categories of auxiliary guest charges and incidentals."""
    DINING = "Dining"
    MINIBAR = "Minibar"
    SPA = "Spa"
    PARKING = "Parking"
    LAUNDRY = "Laundry"
    MISCELLANEOUS = "Miscellaneous"


class FolioChargeStatus(str, Enum):
    """Status lifecycle of a folio incidental charge."""
    BILLED = "Billed"
    PAID = "Paid"
    VOIDED = "Voided"


class FolioChargeBase(BaseModel):
    """Base schema for hotel folio incidental charges."""
    service_category: FolioCategory = Field(default=FolioCategory.MISCELLANEOUS, description="Charge classification")
    description: str = Field(..., min_length=3, max_length=200, description="Itemized billing description")
    unit_price: float = Field(..., ge=0.0, description="Unit price per item/service")
    quantity: int = Field(default=1, gt=0, description="Quantity consumed")
    posted_by: Optional[str] = Field("Front Desk Agent", max_length=100, description="Staff member or department who posted charge")


class FolioChargeCreate(FolioChargeBase):
    """Input payload to post a new incidental charge to an active booking."""
    pass


class FolioChargeVoid(BaseModel):
    """Payload to void an erroneous or disputed incidental charge."""
    void_reason: str = Field(..., min_length=3, max_length=250, description="Mandatory audit justification for voiding")


class FolioChargeResponse(FolioChargeBase):
    """Output representation of a posted folio charge."""
    id: int
    booking_id: int
    total_price: float
    status: FolioChargeStatus
    void_reason: Optional[str] = None
    created_at: Optional[str | datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FolioStatementResponse(BaseModel):
    """Consolidated folio statement itemizing room, amenities, incidentals, and net balance."""
    booking_id: int
    guest_id: int
    guest_name: str
    guest_email: str
    room_id: int
    room_number: str
    booking_status: str
    check_in_date: str
    check_out_date: str
    room_base_charge: float
    amenities_charge: float
    discount_amount: float
    coupon_code: Optional[str] = None
    incidentals: List[FolioChargeResponse] = Field(default_factory=list)
    incidentals_total: float
    grand_total: float
    balance_due: float

    model_config = ConfigDict(from_attributes=True)




