
// =============================================================================
// MODULE 7: Room Operations, Out-of-Order Lockouts & Emergency Relocations
// =============================================================================

let _currentLockoutRoomId = null;
let _currentLockoutRoomNumber = null;
let _currentReleaseRoomId = null;
let _currentMoveBooking = null;  // { id, roomId, roomNumber, guestName, checkIn, checkOut }

// ---- Room Ops Cockpit Modal ----

async function openRoomOpsModal() {
  const modal = document.getElementById("roomOpsModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  await fetchRoomOpsDashboard();
}

function closeRoomOpsModal() {
  const modal = document.getElementById("roomOpsModal");
  if (modal) modal.classList.add("hidden");
}

async function fetchRoomOpsDashboard() {
  try {
    const res = await fetch("/api/rooms/operations-dashboard");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    const setEl = function(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; };
    setEl("opsKpiTotal", data.total_rooms);
    setEl("opsKpiAvail", data.available_count);
    setEl("opsKpiOcc",   data.occupied_count);
    setEl("opsKpiClean", data.cleaning_count);
    setEl("opsKpiOoo",   data.out_of_order_count);
    setEl("opsKpiOos",   data.out_of_service_count);

    // Active Lockouts table
    const lockoutsBody = document.getElementById("activeLockoutsTableBody");
    if (lockoutsBody) {
      if (!data.active_lockouts || data.active_lockouts.length === 0) {
        lockoutsBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:14px;">\u2705 No active room lockouts \u2014 all rooms operational</td></tr>';
      } else {
        lockoutsBody.innerHTML = data.active_lockouts.map(function(l) {
          const pillClass = l.lockout_type === "Out_of_Order" ? "lockout-pill-ooo" : "lockout-pill-oos";
          const typeLabel = l.lockout_type.replace(/_/g, " ");
          const expectedBack = l.expected_completion ? l.expected_completion.split("T")[0] : "\u2014";
          return '<tr>' +
            '<td><strong>Room ' + escapeHtml(l.room_number) + '</strong></td>' +
            '<td><span class="' + pillClass + '">' + typeLabel + '</span></td>' +
            '<td style="max-width:180px;font-size:11px;">' + escapeHtml(l.reason) + '</td>' +
            '<td style="font-size:11px;">' + escapeHtml(l.assigned_trade || "\u2014") + '</td>' +
            '<td style="font-size:11px;">' + expectedBack + '</td>' +
            '<td style="font-size:11px;">' + escapeHtml(l.authorized_by || "\u2014") + '</td>' +
            '<td><button type="button" class="btn btn-release-room" style="font-size:10.5px;padding:3px 8px;"' +
            ' onclick="openRoomReleaseModal(' + l.room_id + ', \'' + escapeHtml(l.room_number) + '\')">Release</button></td>' +
            '</tr>';
        }).join("");
      }
    }

    // Recent Moves table
    const movesBody = document.getElementById("recentRoomMovesTableBody");
    if (movesBody) {
      if (!data.recent_room_moves || data.recent_room_moves.length === 0) {
        movesBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:14px;">No emergency relocations recorded yet.</td></tr>';
      } else {
        movesBody.innerHTML = data.recent_room_moves.map(function(m) {
          const ts = m.relocated_at ? m.relocated_at.replace("T", " ").slice(0, 16) : "\u2014";
          return '<tr>' +
            '<td>#' + m.booking_id + '</td>' +
            '<td style="font-size:11px;">' + escapeHtml(m.guest_name) + '</td>' +
            '<td>Room ' + escapeHtml(m.old_room_number) + ' \u2192 Room ' + escapeHtml(m.new_room_number) + '</td>' +
            '<td style="font-size:11px;max-width:150px;">' + escapeHtml(m.reason) + '</td>' +
            '<td style="font-size:11px;">' + escapeHtml(m.relocated_by) + '</td>' +
            '<td style="text-align:center;">' + m.keycards_reassigned_count + '</td>' +
            '<td style="font-size:10.5px;font-family:monospace;">' + ts + '</td>' +
            '</tr>';
        }).join("");
      }
    }
  } catch (err) {
    showToast("Room Ops load error: " + err.message, "error");
  }
}

// ---- Declare Room Lockout Modal ----

function openRoomLockoutModal(roomId, roomNumber) {
  _currentLockoutRoomId = roomId || null;
  _currentLockoutRoomNumber = roomNumber || null;

  const modal = document.getElementById("roomLockoutModal");
  if (!modal) return;

  const select = document.getElementById("lockoutRoomSelect");
  if (select) {
    select.innerHTML = '<option value="">Select Room...</option>';
    allRoomsData
      .filter(function(r) { return r.status !== "Occupied" && r.status !== "Maintenance"; })
      .forEach(function(r) {
        const opt = document.createElement("option");
        opt.value = r.id;
        opt.textContent = "Room " + r.room_number + " (" + r.room_type + ") \u2014 " + r.status;
        if (roomId && r.id === roomId) opt.selected = true;
        select.appendChild(opt);
      });
    if (roomId) select.value = roomId;
  }

  const form = document.getElementById("roomLockoutForm");
  if (form) form.reset();
  if (roomId && select) select.value = roomId;

  modal.classList.remove("hidden");
}

function closeRoomLockoutModal() {
  const modal = document.getElementById("roomLockoutModal");
  if (modal) modal.classList.add("hidden");
  _currentLockoutRoomId = null;
}

async function handleRoomLockoutSubmit(e) {
  e.preventDefault();
  const select = document.getElementById("lockoutRoomSelect");
  const roomId = parseInt(select ? select.value : (_currentLockoutRoomId || 0), 10);
  if (!roomId) { showToast("Please select a room to lock out.", "error"); return; }

  const payload = {
    lockout_type: (document.getElementById("lockoutType") || {}).value || "Out_of_Order",
    reason: ((document.getElementById("lockoutReason") || {}).value || "").trim(),
    assigned_trade: (document.getElementById("lockoutTrade") || {}).value || "General Maintenance",
    authorized_by: ((document.getElementById("lockoutAuthorizedBy") || {}).value || "Duty Manager").trim(),
    expected_completion: (document.getElementById("lockoutExpectedCompletion") || {}).value || null,
    notes: ((document.getElementById("lockoutNotes") || {}).value || "").trim(),
  };

  if (!payload.reason) { showToast("Please enter a defect description.", "error"); return; }

  const btn = document.getElementById("btnSubmitRoomLockout");
  if (btn) { btn.disabled = true; btn.textContent = "Locking out..."; }

  try {
    const res = await fetch("/api/rooms/" + roomId + "/lockout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "HTTP " + res.status);

    showToast("\uD83D\uDD12 Room " + data.room_number + " locked out (" + data.lockout_type.replace(/_/g," ") + ").", "success");
    closeRoomLockoutModal();
    fetchRooms();
    fetchKPIs();
  } catch (err) {
    showToast("Lockout failed: " + err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Lock Out Room"; }
  }
}

// ---- Release Room Lockout Modal ----

function openRoomReleaseModal(roomId, roomNumber) {
  _currentReleaseRoomId = roomId;
  const modal = document.getElementById("roomReleaseModal");
  if (!modal) return;

  const display = document.getElementById("releaseRoomDisplay");
  if (display) display.value = "Room " + roomNumber;
  const hiddenId = document.getElementById("releaseRoomId");
  if (hiddenId) hiddenId.value = roomId;

  const notes = document.getElementById("releaseNotes");
  if (notes) notes.value = "";

  modal.classList.remove("hidden");
}

function closeRoomReleaseModal() {
  const modal = document.getElementById("roomReleaseModal");
  if (modal) modal.classList.add("hidden");
  _currentReleaseRoomId = null;
}

async function handleRoomReleaseSubmit(e) {
  e.preventDefault();
  const roomId = (document.getElementById("releaseRoomId") || {}).value || _currentReleaseRoomId;
  if (!roomId) { showToast("No room selected for release.", "error"); return; }

  const payload = {
    released_by: ((document.getElementById("releaseCertifiedBy") || {}).value || "Facilities Supervisor").trim(),
    target_cleanliness: (document.getElementById("releaseCleanliness") || {}).value || "Touch-up Required",
    resolution_notes: ((document.getElementById("releaseNotes") || {}).value || "").trim(),
  };

  if (!payload.resolution_notes) { showToast("Please enter resolution certification notes.", "error"); return; }

  const btn = document.getElementById("btnSubmitRoomRelease");
  if (btn) { btn.disabled = true; btn.textContent = "Certifying..."; }

  try {
    const res = await fetch("/api/rooms/" + roomId + "/release", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "HTTP " + res.status);

    showToast("\u2705 Room released to Cleaning. Turnover triggered.", "success");
    closeRoomReleaseModal();
    const opsModal = document.getElementById("roomOpsModal");
    if (opsModal && !opsModal.classList.contains("hidden")) fetchRoomOpsDashboard();
    fetchRooms();
    fetchKPIs();
    if (typeof fetchHousekeepingDashboard === "function") fetchHousekeepingDashboard();
  } catch (err) {
    showToast("Release failed: " + err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Certify & Release Room"; }
  }
}

// ---- Emergency Room Move Modal ----

async function openRoomMoveModal(bookingId) {
  try {
    const res = await fetch("/api/bookings/" + bookingId);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const b = await res.json();

    _currentMoveBooking = {
      id: bookingId,
      roomId: b.room_id,
      roomNumber: b.room ? b.room.room_number : b.room_id,
      guestName: b.guest ? b.guest.first_name + " " + b.guest.last_name : "Guest #" + b.guest_id,
      checkIn: b.check_in_date,
      checkOut: b.check_out_date,
    };

    const modal = document.getElementById("roomMoveModal");
    if (!modal) return;

    const nameEl  = document.getElementById("moveGuestName");
    const roomEl  = document.getElementById("moveOldRoomDisplay");
    const datesEl = document.getElementById("moveStayDates");
    const hiddenId = document.getElementById("moveBookingId");

    if (nameEl)  nameEl.textContent  = _currentMoveBooking.guestName;
    if (roomEl)  roomEl.textContent  = "Currently in Room " + _currentMoveBooking.roomNumber;
    if (datesEl) datesEl.textContent = _currentMoveBooking.checkIn + " \u2192 " + _currentMoveBooking.checkOut;
    if (hiddenId) hiddenId.value = bookingId;

    const targetSelect = document.getElementById("moveTargetRoomSelect");
    if (targetSelect) {
      targetSelect.innerHTML = '<option value="">Select Available Clean Room...</option>';
      allRoomsData
        .filter(function(r) { return r.status === "Available" && r.id !== _currentMoveBooking.roomId; })
        .forEach(function(r) {
          const opt = document.createElement("option");
          opt.value = r.id;
          opt.textContent = "Room " + r.room_number + " \u2014 " + r.room_type + " (" + r.cleanliness_status + ")";
          targetSelect.appendChild(opt);
        });
    }

    const reasonEl = document.getElementById("moveReason");
    if (reasonEl) reasonEl.value = "";
    const relocatedByEl = document.getElementById("moveRelocatedBy");
    if (relocatedByEl) relocatedByEl.value = "Front Desk Duty Manager";

    modal.classList.remove("hidden");
  } catch (err) {
    showToast("Failed to load booking: " + err.message, "error");
  }
}

function closeRoomMoveModal() {
  const modal = document.getElementById("roomMoveModal");
  if (modal) modal.classList.add("hidden");
  _currentMoveBooking = null;
}

async function handleRoomMoveSubmit(e) {
  e.preventDefault();
  const bookingId = (document.getElementById("moveBookingId") || {}).value || (_currentMoveBooking && _currentMoveBooking.id);
  if (!bookingId) return;

  const newRoomId = parseInt((document.getElementById("moveTargetRoomSelect") || {}).value || "0", 10);
  if (!newRoomId) { showToast("Please select a target destination room.", "error"); return; }

  const reason = ((document.getElementById("moveReason") || {}).value || "").trim();
  if (!reason) { showToast("Please enter the relocation reason.", "error"); return; }

  const payload = {
    new_room_id: newRoomId,
    reason: reason,
    relocated_by: ((document.getElementById("moveRelocatedBy") || {}).value || "Front Desk Duty Manager").trim(),
    transfer_keycards: (document.getElementById("moveTransferKeycards") || { checked: true }).checked,
    old_room_lockout: (document.getElementById("moveOldRoomLockout") || { checked: true }).checked,
  };

  const btn = document.getElementById("btnSubmitRoomMove");
  if (btn) { btn.disabled = true; btn.textContent = "Relocating..."; }

  try {
    const res = await fetch("/api/bookings/" + bookingId + "/room-move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "HTTP " + res.status);

    showToast(
      "\uD83D\uDE80 Guest relocated: Room " + data.old_room_number + " \u2192 Room " + data.new_room_number + ". " +
      (data.keycards_reassigned_count > 0 ? "Keycards re-encoded." : ""),
      "success"
    );
    closeRoomMoveModal();
    fetchBookings();
    fetchRooms();
    fetchKPIs();
  } catch (err) {
    showToast("Relocation failed: " + err.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Execute Relocation"; }
  }
}
