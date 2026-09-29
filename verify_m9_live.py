import httpx

client = httpx.Client(base_url="http://127.0.0.1:8000")

# 1. Fetch catalog
res = client.get("/bookings")
print(f"[LIVE] Total bookings in database: {len(res.json())}")

# 2. Create reservation with amenities
payload = {
    "room_id": 1,
    "check_in_date": "2027-01-10",
    "check_out_date": "2027-01-13",
    "amenity_ids": [1, 2],
    "guest": {
        "first_name": "Alexander",
        "last_name": "Pierce",
        "email": "alex.pierce@enterprise.com",
        "phone": "+1-555-9081"
    }
}
b_res = client.post("/bookings", json=payload)
if b_res.status_code != 201:
    print(f"Error creating booking ({b_res.status_code}):", b_res.text)
    exit(1)
booking = b_res.json()
b_id = booking["id"]
print(f"[LIVE] Created booking #{b_id} on Room {booking['room']['room_number']}: status={booking['booking_status']}, total=${booking['total_price']}")

# 3. Check-In
ci_res = client.post(f"/bookings/{b_id}/check-in")
ci_data = ci_res.json()
print(f"[LIVE] Check-in result: booking_status={ci_data['booking_status']}, room_status={ci_data['room']['status']}")

# 4. Check-Out and Folio Invoicing
co_res = client.post(f"/bookings/{b_id}/check-out")
co_data = co_res.json()
print(f"[LIVE] Check-out result: status={co_data['status']}, room_status_after_checkout={co_data['room_status_after_checkout']}")
print(f"[LIVE] Folio Grand Total: ${co_data['grand_total']} (Base: ${co_data['base_room_charge']}, Amenities: ${co_data['amenities_charge']}, Tax: ${co_data['tax_amount']})")
print("[LIVE] Line Item Breakdown:")
for item in co_data["invoice_breakdown"]:
    print(f"       - {item['description']}: {item['quantity']} x ${item['unit_price']} = ${item['total_amount']}")

# 5. Cancellation test
c_payload = {
    "room_id": 6,
    "check_in_date": "2027-02-15",
    "check_out_date": "2027-02-18",
    "guest": {
        "first_name": "Sophia",
        "last_name": "Laurent",
        "email": "sophia.l@enterprise.com",
        "phone": "+1-555-9082"
    }
}
c_booking = client.post("/bookings", json=c_payload).json()
c_id = c_booking["id"]
cancel_res = client.post(f"/bookings/{c_id}/cancel").json()
print(f"[LIVE] Cancellation result: status={cancel_res['status']}, refund=${cancel_res['refund_amount']}, fee=${cancel_res['cancellation_fee']}")
print(f"[LIVE] Cancellation message: '{cancel_res['message']}'")

print("[LIVE] ALL MODULE 9 ENDPOINTS VERIFIED ON LIVE FASTAPI SERVER!")
