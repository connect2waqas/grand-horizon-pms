"""
verify_schemas.py - Verification script for Pydantic models & validation rules.
"""
from datetime import date
from pydantic import ValidationError
from schemas import (
    GuestCreate, GuestResponse,
    RoomCreate, RoomResponse, RoomType, RoomStatus,
    BookingCreate, BookingResponse, BookingStatus
)

def verify() -> None:
    # 1. Test Valid GuestCreate and GuestResponse serialization
    guest_input = GuestCreate(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+1-555-0199"
    )
    assert not hasattr(guest_input, "id") or "id" not in guest_input.model_fields, "GuestCreate should not have 'id' field"
    print("[PASS] GuestCreate schema created without client-side ID.")

    guest_output = GuestResponse(
        id=1,
        created_at="2026-09-29 10:00:00",
        **guest_input.model_dump()
    )
    assert guest_output.id == 1
    print("[PASS] GuestResponse successfully serializes database identity.")

    # 2. Test Invalid Email validation
    try:
        GuestCreate(first_name="Bad", last_name="Email", email="not-an-email", phone="1234567")
        raise AssertionError("Failed to catch invalid email")
    except ValidationError:
        print("[PASS] Invalid email rejected by Pydantic EmailStr validation.")

    # 3. Test Room Creation & Enum validation
    room_input = RoomCreate(
        room_number="101",
        room_type=RoomType.SINGLE,
        price_per_night=79.99,
        status=RoomStatus.AVAILABLE
    )
    print(f"[PASS] RoomCreate validated: Room {room_input.room_number} ({room_input.room_type.value})")

    try:
        RoomCreate(
            room_number="999",
            room_type="Presidential",  # type: ignore
            price_per_night=999.0
        )
        raise AssertionError("Failed to catch invalid room_type enum")
    except ValidationError:
        print("[PASS] Invalid room_type rejected by RoomType enum constraint.")

    # 4. Test Booking Validation: Temporal validation (checkout must be after checkin)
    try:
        BookingCreate(
            room_id=1,
            guest_id=1,
            check_in_date=date(2026, 10, 5),
            check_out_date=date(2026, 10, 1)  # Invalid: checkout before checkin
        )
        raise AssertionError("Failed to catch checkout <= checkin")
    except ValidationError:
        print("[PASS] Booking date order validation caught checkout <= checkin.")

    # 5. Test Booking Validation: Require at least guest_id or nested guest
    try:
        BookingCreate(
            room_id=1,
            check_in_date=date(2026, 10, 1),
            check_out_date=date(2026, 10, 5)
            # Neither guest_id nor guest provided!
        )
        raise AssertionError("Failed to catch missing guest identity in BookingCreate")
    except ValidationError:
        print("[PASS] BookingCreate requires guest_id or nested guest payload.")

    # 6. Test Valid BookingCreate with nested guest payload
    valid_booking = BookingCreate(
        room_id=1,
        check_in_date=date(2026, 10, 1),
        check_out_date=date(2026, 10, 5),
        guest=guest_input
    )
    assert valid_booking.guest.email == "jane.doe@example.com"
    print("[PASS] BookingCreate with nested guest payload validated successfully.")

    # 7. Test BookingResponse representation
    booking_resp = BookingResponse(
        id=42,
        guest_id=1,
        room_id=1,
        check_in_date=valid_booking.check_in_date,
        check_out_date=valid_booking.check_out_date,
        total_price=319.96,
        booking_status=BookingStatus.CONFIRMED,
        guest=guest_output,
        room=RoomResponse(id=1, **room_input.model_dump())
    )
    assert booking_resp.total_price == 319.96
    print(f"[PASS] BookingResponse generated with ID #{booking_resp.id} and total ${booking_resp.total_price}.")

    print("\nAll Pydantic schema validation rules verified successfully!")

if __name__ == "__main__":
    verify()
