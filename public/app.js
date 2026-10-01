/**
 * app.js - Enterprise Hotel Management Dashboard Controller
 * 
 * Handles:
 * 1. Top-Level Executive KPI Bar (GET /stats)
 * 2. Instant Reactive Filtering by Category & Date bounds
 * 3. Streamlined Booking Flow (Direct card selection with auto-focus)
 * 4. Dynamic Room States (Available, Occupied, Cleaning)
 * 5. Reservation Submission & Confirmation Modal
 */

// Global State
let allRoomsData = [];
let selectedRoomId = null;

// DOM Elements: KPIs
const kpiTotalRooms = document.getElementById("kpiTotalRooms");
const kpiOccupancy = document.getElementById("kpiOccupancy");
const kpiCheckins = document.getElementById("kpiCheckins");
const kpiRevenue = document.getElementById("kpiRevenue");
const kpiInventorySub = document.getElementById("kpiInventorySub");
const kpiAdrRevpar = document.getElementById("kpiAdrRevpar");
const kpiTurnoverSub = document.getElementById("kpiTurnoverSub");
const kpiMonthlyRev = document.getElementById("kpiMonthlyRev");

// DOM Elements: Catalog & Filters
const roomsGrid = document.getElementById("roomsGrid");
const loadingState = document.getElementById("loadingState");
const emptyState = document.getElementById("emptyState");
const refreshRoomsBtn = document.getElementById("refreshRoomsBtn");

const filterCheckIn = document.getElementById("filterCheckIn");
const filterCheckOut = document.getElementById("filterCheckOut");
const filterType = document.getElementById("filterType");
const filterFloor = document.getElementById("filterFloor");
const filterCleanliness = document.getElementById("filterCleanliness");
const filterMaintenance = document.getElementById("filterMaintenance");
const applyFilterBtn = document.getElementById("applyFilterBtn");
const resetFilterBtn = document.getElementById("resetFilterBtn");

// DOM Elements: Booking Form & Streamlined Banner
const bookingForm = document.getElementById("bookingForm");
const selectedRoomIdInput = document.getElementById("selectedRoomId");
const selectedRoomBanner = document.getElementById("selectedRoomBanner");
const selectedRoomPill = document.getElementById("selectedRoomPill");
const selectedRoomName = document.getElementById("selectedRoomName");
const selectedRoomRate = document.getElementById("selectedRoomRate");

const bookingCheckIn = document.getElementById("bookingCheckIn");
const bookingCheckOut = document.getElementById("bookingCheckOut");
const btnAutoAssign = document.getElementById("btnAutoAssign");
const autoAssignBadge = document.getElementById("autoAssignBadge");
const bookingAdults = document.getElementById("bookingAdults");
const bookingChildren = document.getElementById("bookingChildren");
const bookingETA = document.getElementById("bookingETA");
const bookingGuarantee = document.getElementById("bookingGuarantee");
const bookingEarlyCheckin = document.getElementById("bookingEarlyCheckin");
const bookingLateCheckout = document.getElementById("bookingLateCheckout");
const bookingSpecialRequests = document.getElementById("bookingSpecialRequests");
const guestFirstName = document.getElementById("guestFirstName");
const guestLastName = document.getElementById("guestLastName");
const guestEmail = document.getElementById("guestEmail");
const guestPhone = document.getElementById("guestPhone");
const submitBookingBtn = document.getElementById("submitBookingBtn");
const btnText = submitBookingBtn.querySelector(".btn-text");
const btnSpinner = submitBookingBtn.querySelector(".btn-spinner");

const rateCalculation = document.getElementById("rateCalculation");
const estimateTotal = document.getElementById("estimateTotal");

// DOM Elements: Module 3 Rate Plans & Yield Management
const bookingRatePlan = document.getElementById("bookingRatePlan");
const ratePlanBadge = document.getElementById("ratePlanBadge");
const ratePlanPolicyText = document.getElementById("ratePlanPolicyText");

// DOM Elements: Module 11 Dynamic Pricing & Promotional Coupons
const couponCodeInput = document.getElementById("couponCodeInput");
const btnApplyCoupon = document.getElementById("btnApplyCoupon");
const couponStatusMessage = document.getElementById("couponStatusMessage");
const toggleDynamicPricing = document.getElementById("toggleDynamicPricing");
const quoteBreakdownContainer = document.getElementById("quoteBreakdownContainer");
const pricingEngineStatus = document.getElementById("pricingEngineStatus");
const promoChips = document.querySelectorAll(".promo-chip");


// DOM Elements: Receipt Modal & Toasts
const receiptModal = document.getElementById("receiptModal");
const modalDetails = document.getElementById("modalDetails");
const closeModalBtn = document.getElementById("closeModalBtn");
const toastContainer = document.getElementById("toastContainer");

// DOM Elements: Front Desk & Reservations Lifecycle
const bookingFilterTabs = document.getElementById("bookingFilterTabs");
const reservationsTableBody = document.getElementById("reservationsTableBody");
const reservationsEmpty = document.getElementById("reservationsEmpty");
const invoiceModal = document.getElementById("invoiceModal");
const invoiceDetails = document.getElementById("invoiceDetails");
const invoiceSubtitle = document.getElementById("invoiceSubtitle");
const closeInvoiceBtn = document.getElementById("closeInvoiceBtn");

// DOM Elements: Module 10 Guest CRM & Loyalty
const guestSearchInput = document.getElementById("guestSearchInput");
const guestTierTabs = document.getElementById("guestTierTabs");
const guestsTableBody = document.getElementById("guestsTableBody");
const guestsEmpty = document.getElementById("guestsEmpty");
const btnOpenNewGuestModal = document.getElementById("btnOpenNewGuestModal");
const guestDetailModal = document.getElementById("guestDetailModal");
const guestDetailBody = document.getElementById("guestDetailBody");
const closeGuestDetailBtn = document.getElementById("closeGuestDetailBtn");
const newGuestModal = document.getElementById("newGuestModal");
const newGuestForm = document.getElementById("newGuestForm");
const btnCancelNewGuest = document.getElementById("btnCancelNewGuest");

// DOM Elements: Module 12 Operations Audit Trail
const auditEntityTabs = document.getElementById("auditEntityTabs");
const auditLogsTableBody = document.getElementById("auditLogsTableBody");
const auditLogsEmpty = document.getElementById("auditLogsEmpty");
const btnRefreshAuditLogs = document.getElementById("btnRefreshAuditLogs");

// DOM Elements: Module 13 Maintenance & Work Orders
const maintenanceStatusTabs = document.getElementById("maintenanceStatusTabs");
const maintenanceTableBody = document.getElementById("maintenanceTableBody");
const maintenanceEmpty = document.getElementById("maintenanceEmpty");
const mKpiOpen = document.getElementById("mKpiOpen");
const mKpiProgress = document.getElementById("mKpiProgress");
const mKpiUrgent = document.getElementById("mKpiUrgent");
const mKpiResolved = document.getElementById("mKpiResolved");
const btnOpenNewTicketModal = document.getElementById("btnOpenNewTicketModal");
const newTicketModal = document.getElementById("newTicketModal");
const newTicketForm = document.getElementById("newTicketForm");
const btnCancelNewTicket = document.getElementById("btnCancelNewTicket");
const ticketRoomSelect = document.getElementById("ticketRoomSelect");
const resolveTicketModal = document.getElementById("resolveTicketModal");
const resolveTicketForm = document.getElementById("resolveTicketForm");
const btnCancelResolveTicket = document.getElementById("btnCancelResolveTicket");
const resolveTicketId = document.getElementById("resolveTicketId");
const resolveNotes = document.getElementById("resolveNotes");
const resolveAutoRelease = document.getElementById("resolveAutoRelease");
const resolveModalTitle = document.getElementById("resolveModalTitle");
const resolveModalSubtitle = document.getElementById("resolveModalSubtitle");

// ==========================================
// Initialization
// ==========================================

document.addEventListener("DOMContentLoaded", () => {
  setupInitialDates();
  fetchKPIs();
  fetchRooms();
  fetchBookings();
  fetchGuests();
  fetchAuditLogs();
  fetchMaintenanceTickets();
  fetchMaintenanceSummary();
  fetchHousekeepingDashboard();
  fetchHousekeepingTasks();
  fetchSecurityDashboard();
  fetchKeycards();
  fetchAccessLogs();
  setupEventListeners();
});

function setupInitialDates() {
  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const todayStr = today.toISOString().split("T")[0];
  const tomorrowStr = tomorrow.toISOString().split("T")[0];

  bookingCheckIn.min = todayStr;
  bookingCheckOut.min = tomorrowStr;
  bookingCheckIn.value = todayStr;
  bookingCheckOut.value = tomorrowStr;

  filterCheckIn.min = todayStr;
  filterCheckOut.min = tomorrowStr;
}

function setupEventListeners() {
  refreshRoomsBtn.addEventListener("click", () => {
    fetchKPIs();
    fetchRooms();
  });

  // 1. Instant Reactive Filtering by Category, Floor, and Cleanliness
  filterType.addEventListener("change", applyCurrentFilters);
  if (filterFloor) filterFloor.addEventListener("change", applyCurrentFilters);
  if (filterCleanliness) filterCleanliness.addEventListener("change", applyCurrentFilters);

  // Maintenance visibility filter
  if (filterMaintenance) {
    filterMaintenance.addEventListener("change", () => {
      fetchRooms(filterCheckIn.value || null, filterCheckOut.value || null);
    });
  }

  // Date availability filter
  applyFilterBtn.addEventListener("click", () => {
    if (filterCheckIn.value && filterCheckOut.value) {
      if (filterCheckOut.value <= filterCheckIn.value) {
        showToast("Check-out date must be after check-in date.", "error");
        return;
      }
      fetchRooms(filterCheckIn.value, filterCheckOut.value);
    } else {
      applyCurrentFilters();
    }
  });

  resetFilterBtn.addEventListener("click", () => {
    filterCheckIn.value = "";
    filterCheckOut.value = "";
    filterType.value = "";
    if (filterFloor) filterFloor.value = "";
    if (filterCleanliness) filterCleanliness.value = "";
    if (filterMaintenance) filterMaintenance.checked = false;
    fetchRooms();
  });

  // Price Estimator triggers
  bookingCheckIn.addEventListener("change", () => {
    if (bookingCheckIn.value) {
      const nextDay = new Date(bookingCheckIn.value);
      nextDay.setDate(nextDay.getDate() + 1);
      const nextDayStr = nextDay.toISOString().split("T")[0];
      bookingCheckOut.min = nextDayStr;
      if (bookingCheckOut.value && bookingCheckOut.value <= bookingCheckIn.value) {
        bookingCheckOut.value = nextDayStr;
      }
    }
    updateCostEstimate();
  });

  bookingCheckOut.addEventListener("change", updateCostEstimate);

  // Module 3 Rate Plan & Policy Listener
  if (bookingRatePlan) {
    bookingRatePlan.addEventListener("change", () => {
      const code = bookingRatePlan.value;
      if (code === "BAR") {
        if (ratePlanBadge) ratePlanBadge.textContent = "BAR • 1.0x";
        if (ratePlanPolicyText) ratePlanPolicyText.textContent = "Flexible 24h free cancellation • Room Only • Min 1 night";
      } else if (code === "NON_REF") {
        if (ratePlanBadge) ratePlanBadge.textContent = "NON_REF • 0.85x";
        if (ratePlanPolicyText) ratePlanPolicyText.textContent = "Non-Refundable (Deposit locked) • 15% Savings • Room Only";
      } else if (code === "BB_PACKAGE") {
        if (ratePlanBadge) ratePlanBadge.textContent = "BB_PACKAGE • 1.15x";
        if (ratePlanPolicyText) ratePlanPolicyText.textContent = "Flexible cancellation • Includes Gourmet Continental Breakfast";
      } else if (code === "CORP_EXTENDED") {
        if (ratePlanBadge) ratePlanBadge.textContent = "CORP_EXTENDED • 0.80x";
        if (ratePlanPolicyText) ratePlanPolicyText.textContent = "Moderate 48h cancellation • 20% Savings • Min 3 nights required";
      }
      updateCostEstimate();
    });
  }

  // Module 11 Dynamic Pricing & Coupon Listeners
  if (toggleDynamicPricing) {
    toggleDynamicPricing.addEventListener("change", updateCostEstimate);
  }
  if (btnApplyCoupon) {
    btnApplyCoupon.addEventListener("click", handleApplyCoupon);
  }
  if (couponCodeInput) {
    couponCodeInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleApplyCoupon();
      }
    });
    couponCodeInput.addEventListener("input", () => {
      // Clear status message when typing new code
      if (couponStatusMessage) couponStatusMessage.classList.add("hidden");
    });
  }
  if (promoChips) {
    promoChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        if (couponCodeInput) {
          couponCodeInput.value = chip.dataset.code;
          handleApplyCoupon();
        }
      });
    });
  }

  // Module 2: Auto-Assign room trigger
  if (btnAutoAssign) {
    btnAutoAssign.addEventListener("click", handleAutoAssign);
  }

  // Form submission
  bookingForm.addEventListener("submit", handleBookingSubmit);

  // Modal dismissal
  closeModalBtn.addEventListener("click", () => receiptModal.classList.add("hidden"));
  receiptModal.addEventListener("click", (e) => {
    if (e.target === receiptModal) receiptModal.classList.add("hidden");
  });

  // Filter tabs for front desk reservations
  if (bookingFilterTabs) {
    bookingFilterTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".tab-btn");
      if (!tab) return;
      bookingFilterTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      tab.classList.add("active");
      fetchBookings(tab.dataset.status);
    });
  }

  // Invoice modal dismissal
  if (closeInvoiceBtn) {
    closeInvoiceBtn.addEventListener("click", () => invoiceModal.classList.add("hidden"));
    invoiceModal.addEventListener("click", (e) => {
      if (e.target === invoiceModal) invoiceModal.classList.add("hidden");
    });
  }

  // Module 14: Folio Modal Dismissal & Presets
  const folioModal = document.getElementById("folioModal");
  const btnCloseFolioModal = document.getElementById("btnCloseFolioModal");
  const folioChargeForm = document.getElementById("folioChargeForm");

  if (btnCloseFolioModal && folioModal) {
    btnCloseFolioModal.addEventListener("click", () => folioModal.classList.add("hidden"));
    folioModal.addEventListener("click", (e) => {
      if (e.target === folioModal) folioModal.classList.add("hidden");
    });
  }

  if (folioChargeForm) {
    folioChargeForm.addEventListener("submit", handlePostFolioCharge);
  }

  document.querySelectorAll("#folioPresetChips .preset-pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      const catSelect = document.getElementById("chargeCategorySelect");
      const descInput = document.getElementById("chargeDescInput");
      const priceInput = document.getElementById("chargePriceInput");
      const qtyInput = document.getElementById("chargeQtyInput");
      if (catSelect) catSelect.value = btn.dataset.cat;
      if (descInput) descInput.value = btn.dataset.desc;
      if (priceInput) priceInput.value = btn.dataset.price;
      if (qtyInput) qtyInput.value = "1";
    });
  });

  // Module 10: Guest CRM Search (Debounced)
  let searchTimeout = null;
  if (guestSearchInput) {
    guestSearchInput.addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        const activeTier = guestTierTabs.querySelector(".tab-btn.active")?.dataset.tier || "";
        fetchGuests(e.target.value, activeTier);
      }, 250);
    });
  }

  // Module 10: Guest Tier Filter Tabs
  if (guestTierTabs) {
    guestTierTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".tab-btn");
      if (!tab) return;
      guestTierTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      tab.classList.add("active");
      const q = guestSearchInput ? guestSearchInput.value : "";
      fetchGuests(q, tab.dataset.tier);
    });
  }

  // Module 10: New Guest Modal Open / Close / Submit
  if (btnOpenNewGuestModal) {
    btnOpenNewGuestModal.addEventListener("click", () => {
      newGuestForm.reset();
      newGuestModal.classList.remove("hidden");
    });
  }
  if (btnCancelNewGuest) {
    btnCancelNewGuest.addEventListener("click", () => newGuestModal.classList.add("hidden"));
  }
  if (newGuestModal) {
    newGuestModal.addEventListener("click", (e) => {
      if (e.target === newGuestModal) newGuestModal.classList.add("hidden");
    });
  }
  if (newGuestForm) {
    newGuestForm.addEventListener("submit", handleCreateNewGuest);
  }

  // Module 10: Guest Detail Modal Dismissal
  if (closeGuestDetailBtn) {
    closeGuestDetailBtn.addEventListener("click", () => guestDetailModal.classList.add("hidden"));
  }
  if (guestDetailModal) {
    guestDetailModal.addEventListener("click", (e) => {
      if (e.target === guestDetailModal) guestDetailModal.classList.add("hidden");
    });
  }

  // Module 12: Audit Trail Entity Filter Tabs
  if (auditEntityTabs) {
    auditEntityTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".tab-btn");
      if (!tab) return;
      auditEntityTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      tab.classList.add("active");
      fetchAuditLogs(tab.dataset.entity);
    });
  }

  // Module 12: Refresh Audit Logs Button
  if (btnRefreshAuditLogs) {
    btnRefreshAuditLogs.addEventListener("click", () => {
      const activeEntity = auditEntityTabs ? auditEntityTabs.querySelector(".tab-btn.active")?.dataset.entity || "" : "";
      fetchAuditLogs(activeEntity);
    });
  }

  // Module 13: Maintenance Filter Tabs
  if (maintenanceStatusTabs) {
    maintenanceStatusTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".tab-btn");
      if (!tab) return;
      maintenanceStatusTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      tab.classList.add("active");
      fetchMaintenanceTickets(tab.dataset.status);
    });
  }

  // Module 13: New Ticket Modal Open / Close / Submit
  if (btnOpenNewTicketModal) {
    btnOpenNewTicketModal.addEventListener("click", () => {
      populateTicketRoomSelect();
      newTicketForm.reset();
      newTicketModal.classList.remove("hidden");
    });
  }
  if (btnCancelNewTicket) {
    btnCancelNewTicket.addEventListener("click", () => newTicketModal.classList.add("hidden"));
  }
  if (newTicketModal) {
    newTicketModal.addEventListener("click", (e) => {
      if (e.target === newTicketModal) newTicketModal.classList.add("hidden");
    });
  }
  if (newTicketForm) {
    newTicketForm.addEventListener("submit", handleCreateMaintenanceTicket);
  }

  // Module 13: Resolve Ticket Modal Close / Submit
  if (btnCancelResolveTicket) {
    btnCancelResolveTicket.addEventListener("click", () => resolveTicketModal.classList.add("hidden"));
  }
  if (resolveTicketModal) {
    resolveTicketModal.addEventListener("click", (e) => {
      if (e.target === resolveTicketModal) resolveTicketModal.classList.add("hidden");
    });
  }
  if (resolveTicketForm) {
    resolveTicketForm.addEventListener("submit", handleSubmitResolveTicket);
  }

  // Module 4: Housekeeping Status Tabs
  const hkTabs = document.querySelectorAll("#housekeepingStatusTabs .tab-btn");
  hkTabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      hkTabs.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const status = btn.getAttribute("data-status");
      fetchHousekeepingTasks(status);
    });
  });

  // Module 4: Housekeeping Modal triggers
  const btnOpenHkModal = document.getElementById("btnOpenNewHkTaskModal");
  if (btnOpenHkModal) {
    btnOpenHkModal.addEventListener("click", openDispatchHkTaskModal);
  }
  const btnCancelHkModal = document.getElementById("btnCancelHkTaskModal");
  if (btnCancelHkModal) {
    btnCancelHkModal.addEventListener("click", closeDispatchHkTaskModal);
  }
  const dispatchHkModal = document.getElementById("dispatchHkTaskModal");
  if (dispatchHkModal) {
    dispatchHkModal.addEventListener("click", (e) => {
      if (e.target === dispatchHkModal) closeDispatchHkTaskModal();
    });
  }
  const dispatchHkForm = document.getElementById("dispatchHkTaskForm");
  if (dispatchHkForm) {
    dispatchHkForm.addEventListener("submit", handleDispatchHkTaskSubmit);
  }

  // Module 5: Security View Tabs (Keycards vs Access Logs)
  const secViewTabs = document.getElementById("securityViewTabs");
  if (secViewTabs) {
    secViewTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".tab-btn");
      if (!tab) return;
      secViewTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      tab.classList.add("active");

      const view = tab.dataset.view;
      const cardsView = document.getElementById("keycardsTableView");
      const logsView = document.getElementById("accessLogsTableView");

      if (view === "cards") {
        if (cardsView) cardsView.classList.remove("hidden");
        if (logsView) logsView.classList.add("hidden");
        fetchKeycards();
      } else {
        if (cardsView) cardsView.classList.add("hidden");
        if (logsView) logsView.classList.remove("hidden");
        fetchAccessLogs();
      }
    });
  }

  // Module 5: Keycard Search
  const secSearchInput = document.getElementById("secKeycardSearch");
  if (secSearchInput) {
    let secSearchTimer = null;
    secSearchInput.addEventListener("input", (e) => {
      clearTimeout(secSearchTimer);
      secSearchTimer = setTimeout(() => {
        currentSecSearch = e.target.value.trim();
        fetchKeycards();
      }, 250);
    });
  }

  // Module 5: Keycard Status & Type Filter Tabs
  const kcFilterTabs = document.getElementById("keycardStatusFilterTabs");
  if (kcFilterTabs) {
    kcFilterTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".tab-btn");
      if (!tab) return;
      kcFilterTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      tab.classList.add("active");

      currentSecStatusFilter = tab.dataset.status || "";
      currentSecTypeFilter = tab.dataset.type || "";
      fetchKeycards();
    });
  }

  // Module 5: Access Logs Outcome Filter Tabs
  const accessFilterTabs = document.getElementById("accessLogsFilterTabs");
  if (accessFilterTabs) {
    accessFilterTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".tab-btn");
      if (!tab) return;
      accessFilterTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      tab.classList.add("active");

      currentSecOutcomeFilter = tab.dataset.outcome || "";
      fetchAccessLogs();
    });
  }

  // Module 5: Issue Keycard Modal triggers
  const btnOpenIssueKc = document.getElementById("btnOpenIssueCardModal");
  if (btnOpenIssueKc) {
    btnOpenIssueKc.addEventListener("click", openIssueCardModal);
  }
  const btnCancelIssueKc = document.getElementById("btnCancelIssueCardModal");
  if (btnCancelIssueKc) {
    btnCancelIssueKc.addEventListener("click", closeIssueCardModal);
  }
  const issueKcModal = document.getElementById("issueCardModal");
  if (issueKcModal) {
    issueKcModal.addEventListener("click", (e) => {
      if (e.target === issueKcModal) closeIssueCardModal();
    });
  }
  const issueKcForm = document.getElementById("issueKeycardForm");
  if (issueKcForm) {
    issueKcForm.addEventListener("submit", handleIssueKeycardSubmit);
  }

  // Module 5: Door Tap Simulator Modal triggers
  const btnOpenDoorTap = document.getElementById("btnOpenDoorTapModal");
  if (btnOpenDoorTap) {
    btnOpenDoorTap.addEventListener("click", () => openDoorTapModalWithCard());
  }
  const btnCloseDoorTap = document.getElementById("btnCloseDoorTapModal");
  if (btnCloseDoorTap) {
    btnCloseDoorTap.addEventListener("click", closeDoorTapModal);
  }
  const doorTapModal = document.getElementById("doorTapModal");
  if (doorTapModal) {
    doorTapModal.addEventListener("click", (e) => {
      if (e.target === doorTapModal) closeDoorTapModal();
    });
  }
  const btnExecuteTap = document.getElementById("btnExecuteDoorTap");
  if (btnExecuteTap) {
    btnExecuteTap.addEventListener("click", handleExecuteDoorTap);
  }
}

// ==========================================
// 1. Executive KPI Bar (GET /analytics/kpis)
// ==========================================

async function fetchKPIs() {
  try {
    const res = await fetch("/api/analytics/kpis");
    if (!res.ok) throw new Error("Failed to load metrics");
    const data = await res.json();

    if (kpiTotalRooms) kpiTotalRooms.textContent = data.total_rooms;
    if (kpiOccupancy) kpiOccupancy.textContent = data.occupancy_rate_display || `${data.occupancy_rate.toFixed(1)}%`;
    if (kpiCheckins) kpiCheckins.textContent = data.today_checkins;

    const dailyEst = data.estimated_daily_revenue !== undefined ? data.estimated_daily_revenue : (data.total_revenue || 0);
    if (kpiRevenue) {
      kpiRevenue.textContent = `$${dailyEst.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    if (kpiInventorySub) {
      kpiInventorySub.textContent = `${data.available_rooms} Avail • ${data.occupied_rooms} Occ • ${data.cleaning_rooms} Clean • ${data.maintenance_rooms} Maint`;
    }
    if (kpiAdrRevpar) {
      kpiAdrRevpar.textContent = `ADR $${data.adr.toFixed(2)} • RevPAR $${data.revpar.toFixed(2)}`;
    }
    if (kpiTurnoverSub) {
      kpiTurnoverSub.textContent = `${data.today_checkins} Arrival${data.today_checkins === 1 ? '' : 's'} • ${data.today_checkouts} Departure${data.today_checkouts === 1 ? '' : 's'}`;
    }
    if (kpiMonthlyRev) {
      kpiMonthlyRev.textContent = `Total: $${data.total_revenue.toLocaleString("en-US", { minimumFractionDigits: 2 })} • Month: $${data.monthly_revenue.toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
    }
  } catch (err) {
    console.warn("KPI load fallback:", err);
    if (kpiTotalRooms) kpiTotalRooms.textContent = allRoomsData.length || "6";
    if (kpiOccupancy) kpiOccupancy.textContent = "50.0%";
    if (kpiCheckins) kpiCheckins.textContent = "0";
    if (kpiRevenue) kpiRevenue.textContent = "$0.00";
  }
}

// ==========================================
// 2. Fetch Rooms & Reactive Filtering
// ==========================================

async function fetchRooms(checkIn = null, checkOut = null) {
  setLoading(true);

  try {
    const params = new URLSearchParams();
    if (checkIn && checkOut) {
      params.append("check_in_date", checkIn);
      params.append("check_out_date", checkOut);
    }
    if (filterMaintenance && filterMaintenance.checked) {
      params.append("include_maintenance", "true");
    }

    const url = `/api/rooms${params.toString() ? "?" + params.toString() : ""}`;
    const response = await fetch(url);

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server returned HTTP ${response.status}`);
    }

    allRoomsData = await response.json();
    applyCurrentFilters();

    // Auto-select first available room if none currently active
    if (!selectedRoomId) {
      const firstAvailable = allRoomsData.find((r) => r.status === "Available");
      if (firstAvailable) {
        selectRoom(firstAvailable.id, false); // select without stealing focus on initial load
      }
    }
  } catch (error) {
    console.error("Failed to fetch rooms:", error);
    showToast(`Error loading rooms: ${error.message}`, "error");
    roomsGrid.innerHTML = "";
    emptyState.classList.remove("hidden");
  } finally {
    setLoading(false);
  }
}

/**
 * Instantly filters room inventory by selected category, floor, and cleanliness state
 */
function applyCurrentFilters() {
  const selectedCategory = filterType ? filterType.value.trim() : "";
  const selectedFloor = filterFloor ? filterFloor.value.trim() : "";
  const selectedCleanliness = filterCleanliness ? filterCleanliness.value.trim() : "";

  let visibleRooms = allRoomsData;
  if (selectedCategory) {
    visibleRooms = visibleRooms.filter((r) => r.room_type === selectedCategory);
  }
  if (selectedFloor) {
    visibleRooms = visibleRooms.filter((r) => String(r.floor) === selectedFloor);
  }
  if (selectedCleanliness) {
    visibleRooms = visibleRooms.filter((r) => r.cleanliness_status === selectedCleanliness);
  }

  renderRooms(visibleRooms);
}

// ==========================================
// 3. Dynamic Room States & Grid Rendering
// ==========================================

function renderRooms(rooms) {
  if (roomsGrid) {
    roomsGrid.removeAttribute("aria-busy");
    roomsGrid.innerHTML = "";
  }

  if (!rooms || rooms.length === 0) {
    emptyState.classList.remove("hidden");
    return;
  }
  emptyState.classList.add("hidden");

  rooms.forEach((room) => {
    const card = document.createElement("article");
    const isSelected = selectedRoomId === room.id;
    const isAvailable = room.status === "Available";
    const isOccupied = room.status === "Occupied";
    const isCleaning = room.status === "Cleaning";
    const isMaintenance = room.status === "Maintenance";

    // Dynamic state class
    let stateClass = "state-available";
    if (isOccupied) stateClass = "state-occupied";
    if (isCleaning) stateClass = "state-cleaning";
    if (isMaintenance) stateClass = "state-maintenance";

    card.className = `room-card ${stateClass} ${isSelected ? "selected" : ""}`;
    card.dataset.roomId = room.id;

    // Category styling pill
    let categoryClass = "pill-single";
    if (room.room_type === "Double") categoryClass = "pill-double";
    if (room.room_type === "Family Suite") categoryClass = "pill-suite";

    // Status Pill styling
    let statusPillClass = "status-pill-available";
    let statusLabel = "Available";
    let actionBtnHtml = "";

    if (isOccupied) {
      statusPillClass = "status-pill-occupied";
      statusLabel = "Occupied";
      const checkoutText = formatShortDate(room.booked_until) || "Soon";
      actionBtnHtml = `<button type="button" class="btn btn-secondary btn-select-room" disabled>Booked until ${checkoutText}</button>`;
    } else if (isCleaning) {
      statusPillClass = "status-pill-cleaning";
      statusLabel = "Cleaning";
      actionBtnHtml = `<button type="button" class="btn btn-secondary btn-select-room" disabled>In Cleaning</button>`;
    } else if (isMaintenance) {
      statusPillClass = "status-pill-maintenance";
      statusLabel = "Maintenance";
      actionBtnHtml = `<button type="button" class="btn btn-secondary btn-select-room" disabled>Out of Service</button>`;
    } else {
      // Available
      statusPillClass = "status-pill-available";
      statusLabel = "Available";
      actionBtnHtml = `
        <button type="button" class="btn btn-secondary btn-select-room">
          ${isSelected ? "Selected ✓" : "Select Room"}
        </button>
      `;
    }

    // Cleanliness pill badge
    let cleanClass = "cleanliness-inspected";
    let cleanText = "✓ Inspected";
    const cStatus = room.cleanliness_status || "Inspected";
    if (cStatus === "Clean") {
      cleanClass = "cleanliness-clean";
      cleanText = "Clean";
    } else if (cStatus === "Dirty") {
      cleanClass = "cleanliness-dirty";
      cleanText = "Dirty";
    } else if (cStatus === "Touch-up Required") {
      cleanClass = "cleanliness-touchup";
      cleanText = "Touch-up";
    }

    // Architectural Specs
    const floorLabel = room.floor ? `Floor ${room.floor}` : `Floor 1`;
    const bedLabel = room.bed_type || "1 King Bed";
    const occLabel = room.max_occupancy ? `👤 Max ${room.max_occupancy}` : "👤 Max 2";
    const viewLabel = room.view_type || "Courtyard Garden";
    const sqmLbl = room.sq_meters ? `${room.sq_meters}m²` : "35m²";

    // Maintenance Lock Notice
    const lockBannerHtml = (isMaintenance && room.lock_reason)
      ? `<div class="room-lock-banner">🔒 ${escapeHtml(room.lock_reason)}</div>`
      : "";

    card.innerHTML = `
      <div class="card-top">
        <div class="room-badge-group">
          <span class="room-category-pill ${categoryClass}">${room.room_type}</span>
          <span class="room-number">Room ${room.room_number}</span>
        </div>
        <div class="room-status-badges">
          <span class="status-pill ${statusPillClass}">${statusLabel}</span>
          <span class="cleanliness-pill ${cleanClass}">${cleanText}</span>
        </div>
      </div>

      <div class="room-spec-tags">
        <span class="spec-pill spec-pill-floor">${floorLabel}</span>
        <span class="spec-pill spec-pill-occ">${occLabel}</span>
        <span class="spec-pill spec-pill-bed">${bedLabel}</span>
        <span class="spec-pill spec-pill-view">${viewLabel} · ${sqmLbl}</span>
      </div>

      ${lockBannerHtml}

      <div class="card-middle">
        <span class="room-price-val">$${room.price_per_night.toFixed(2)}</span>
        <span class="room-price-period">/ night</span>
      </div>

      <div class="card-bottom">
        ${actionBtnHtml}
      </div>

      <div class="card-quick-actions" onclick="event.stopPropagation()">
        <div class="card-quick-actions-row">
          <span class="quick-action-label">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20h9"></path>
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
            </svg>
            Status
          </span>
          <select class="quick-action-select status-select" data-room-id="${room.id}" aria-label="Change Room Status">
            <option value="Available" ${room.status === "Available" ? "selected" : ""}>Mark Available</option>
            <option value="Cleaning" ${room.status === "Cleaning" ? "selected" : ""}>Mark Cleaning</option>
            <option value="Occupied" ${room.status === "Occupied" ? "selected" : ""}>Mark Occupied</option>
            <option value="Maintenance" ${room.status === "Maintenance" ? "selected" : ""}>Mark Maintenance</option>
          </select>
        </div>
        <div class="card-quick-actions-row" style="margin-top: 6px;">
          <span class="quick-action-label">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            Clean
          </span>
          <select class="quick-action-select cleanliness-select" data-room-id="${room.id}" aria-label="Housekeeping Cleanliness State">
            <option value="Inspected" ${cStatus === "Inspected" ? "selected" : ""}>Inspected</option>
            <option value="Clean" ${cStatus === "Clean" ? "selected" : ""}>Clean</option>
            <option value="Dirty" ${cStatus === "Dirty" ? "selected" : ""}>Dirty</option>
            <option value="Touch-up Required" ${cStatus === "Touch-up Required" ? "selected" : ""}>Touch-up</option>
          </select>
        </div>
      </div>
    `;

    // Bind Quick Action status mutation
    const statusSelect = card.querySelector(".status-select");
    if (statusSelect) {
      statusSelect.addEventListener("change", (e) => {
        e.stopPropagation();
        updateRoomStatus(room.id, e.target.value);
      });
    }

    // Bind Housekeeping inspection mutation
    const cleanlinessSelect = card.querySelector(".cleanliness-select");
    if (cleanlinessSelect) {
      cleanlinessSelect.addEventListener("change", (e) => {
        e.stopPropagation();
        updateRoomHousekeeping(room.id, e.target.value);
      });
    }

    // Only available rooms can be selected
    if (isAvailable) {
      card.addEventListener("click", () => selectRoom(room.id, true));
    } else {
      card.addEventListener("click", () => {
        if (isOccupied) {
          showToast(`Room ${room.room_number} is occupied until ${room.booked_until || "further notice"}.`, "error");
        } else if (isCleaning) {
          showToast(`Room ${room.room_number} is currently being sanitized.`, "info");
        } else if (isMaintenance) {
          showToast(`Room ${room.room_number} is out of service: ${room.lock_reason || "Maintenance"}.`, "error");
        }
      });
    }

    roomsGrid.appendChild(card);
  });
}

/**
 * Updates room housekeeping cleanliness status via PATCH /api/rooms/{roomId}/housekeeping
 */
async function updateRoomHousekeeping(roomId, newCleanliness) {
  try {
    const response = await fetch(`/api/rooms/${roomId}/housekeeping`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cleanliness_status: newCleanliness,
        inspected_by: "Housekeeping Supervisor",
        notes: `Turnover inspection recorded as ${newCleanliness} from Front Desk dashboard.`
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server returned HTTP ${response.status}`);
    }

    const updatedRoom = await response.json();

    // Update in-memory state
    const idx = allRoomsData.findIndex((r) => r.id === roomId);
    if (idx !== -1) {
      allRoomsData[idx] = updatedRoom;
    }

    showToast(`Room ${updatedRoom.room_number} housekeeping marked as ${updatedRoom.cleanliness_status}.`, "success");
    applyCurrentFilters();
    fetchAuditLogs();
    fetchKPIs();
  } catch (error) {
    showToast(`Failed to update housekeeping state: ${error.message}`, "error");
  }
}

/**
 * Mutates a room's operational status via PATCH /rooms/{roomId}/status
 * Updates badge and card dynamics in place and re-syncs KPI metrics.
 */
async function updateRoomStatus(roomId, newStatus) {
  try {
    const response = await fetch(`/api/rooms/${roomId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Server returned HTTP ${response.status}`);
    }

    const updatedRoom = await response.json();

    // Update in-memory state
    const idx = allRoomsData.findIndex((r) => r.id === roomId);
    if (idx !== -1) {
      allRoomsData[idx] = updatedRoom;
    }

    // If the mutated room was currently selected and is no longer Available, deselect it
    if (selectedRoomId === roomId && newStatus !== "Available") {
      selectedRoomId = null;
      selectedRoomIdInput.value = "";
      selectedRoomBanner.classList.add("hidden");
    }

    // Re-render rooms with current category filter and update executive KPIs
    applyCurrentFilters();
    fetchKPIs();
    fetchAuditLogs();
    showToast(`Room ${updatedRoom.room_number} status updated to ${newStatus}.`, "success");
  } catch (error) {
    console.error("Failed to update room status:", error);
    showToast(`Status update failed: ${error.message}`, "error");
    applyCurrentFilters();
  }
}

function formatShortDate(dateStr) {
  if (!dateStr) return null;
  try {
    const parts = dateStr.split("-");
    const d = new Date(parts[0], parts[1] - 1, parts[2]);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch (e) {
    return dateStr;
  }
}

// ==========================================
// 4. Streamlined Booking Selection & Auto-Focus
// ==========================================

/**
 * Selects a room, updates the banner, and focuses the check-in input field
 */
function selectRoom(roomId, shouldFocus = true, roomObj = null) {
  const room = roomObj || allRoomsData.find((r) => r.id === roomId);
  if (!room || room.status === "Maintenance" || room.status === "Out of Order") return;

  selectedRoomId = roomId;
  selectedRoomIdInput.value = roomId;

  // Update visual banner
  selectedRoomBanner.classList.add("active");
  selectedRoomPill.textContent = room.room_type;
  selectedRoomName.textContent = `Room ${room.room_number}`;
  selectedRoomRate.innerHTML = `$${room.price_per_night.toFixed(2)} <span class="rate-sub">/night</span>`;

  // Highlight selected card in the grid
  document.querySelectorAll(".room-card").forEach((card) => {
    const isTarget = parseInt(card.dataset.roomId, 10) === roomId;
    card.classList.toggle("selected", isTarget);
    const btn = card.querySelector(".btn-select-room:not(:disabled)");
    if (btn) btn.textContent = isTarget ? "Selected ✓" : "Select Room";
  });

  updateCostEstimate();

  // Smoothly guide user directly to date input
  if (shouldFocus) {
    bookingCheckIn.focus();
    if (window.innerWidth <= 1024) {
      bookingForm.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
}

/**
 * Module 2: Intelligent Room Auto-Assignment Algorithm
 * Evaluates candidate inventory based on party headcount, room capacity, floor preference, and cleanliness.
 */
async function handleAutoAssign() {
  const checkIn = bookingCheckIn ? bookingCheckIn.value : null;
  const checkOut = bookingCheckOut ? bookingCheckOut.value : null;
  const adults = bookingAdults ? parseInt(bookingAdults.value || 1, 10) : 1;
  const children = bookingChildren ? parseInt(bookingChildren.value || 0, 10) : 0;
  const prefType = filterType ? filterType.value.trim() : null;
  const prefFloor = filterFloor && filterFloor.value ? parseInt(filterFloor.value, 10) : null;

  if (!checkIn || !checkOut) {
    showToast("Please choose check-in and check-out dates before auto-assigning.", "info");
    if (bookingCheckIn) bookingCheckIn.focus();
    return;
  }

  if (checkOut <= checkIn) {
    showToast("Check-out date must be strictly after check-in date.", "error");
    return;
  }

  const payload = {
    check_in_date: checkIn,
    check_out_date: checkOut,
    adults: adults,
    children: children,
    preferred_room_type: prefType || null,
    preferred_floor: prefFloor || null,
  };

  if (btnAutoAssign) {
    btnAutoAssign.disabled = true;
    btnAutoAssign.textContent = "Analyzing inventory...";
  }

  try {
    const res = await fetch("/api/bookings/auto-assign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) {
      showToast(data.detail || "No suitable room found matching party size and dates.", "error");
      if (autoAssignBadge) autoAssignBadge.classList.add("hidden");
      return;
    }

    const assigned = data.assigned_room;
    selectRoom(assigned.id, false, assigned);

    if (autoAssignBadge) {
      autoAssignBadge.innerHTML = `✨ <strong>Smart Assigned: Room ${assigned.room_number}</strong> (${assigned.room_type}) • ${escapeHtml(data.assignment_reason || 'Optimal Fit')}`;
      autoAssignBadge.classList.remove("hidden");
    }

    showToast(`Smart Match: Room ${assigned.room_number} auto-assigned (Score: ${data.score})`, "success");
  } catch (err) {
    console.error("Auto-assign error:", err);
    showToast(`Auto-assignment failed: ${err.message}`, "error");
  } finally {
    if (btnAutoAssign) {
      btnAutoAssign.disabled = false;
      btnAutoAssign.textContent = "⚡ Auto-Assign Best Room";
    }
  }
}

// ==========================================
// 5. Dynamic Cost Estimator & Quote Engine
// ==========================================

let activeQuote = null;

async function updateCostEstimate() {
  if (!selectedRoomId) {
    rateCalculation.textContent = "Select an available room";
    estimateTotal.textContent = "$0.00";
    if (quoteBreakdownContainer) quoteBreakdownContainer.classList.add("hidden");
    return;
  }

  const room = allRoomsData.find((r) => r.id === selectedRoomId);
  if (!room) return;

  const checkIn = bookingCheckIn.value;
  const checkOut = bookingCheckOut.value;

  if (!checkIn || !checkOut) {
    rateCalculation.textContent = "Select stay dates";
    estimateTotal.textContent = "$0.00";
    if (quoteBreakdownContainer) quoteBreakdownContainer.classList.add("hidden");
    return;
  }

  const d1 = new Date(checkIn);
  const d2 = new Date(checkOut);
  const diffTime = d2.getTime() - d1.getTime();
  const nights = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (nights <= 0) {
    rateCalculation.textContent = "Check-out must be after check-in";
    estimateTotal.textContent = "$0.00";
    if (quoteBreakdownContainer) quoteBreakdownContainer.classList.add("hidden");
    return;
  }

  const applyDynamic = toggleDynamicPricing ? toggleDynamicPricing.checked : true;
  const couponCode = couponCodeInput && couponCodeInput.value.trim() ? couponCodeInput.value.trim().toUpperCase() : null;

  if (!applyDynamic && !couponCode) {
    // Standard flat rate without dynamic surge or coupon
    const total = (nights * room.price_per_night).toFixed(2);
    rateCalculation.textContent = `$${room.price_per_night.toFixed(2)} × ${nights} night${nights > 1 ? "s" : ""}`;
    estimateTotal.textContent = `$${total}`;
    if (pricingEngineStatus) pricingEngineStatus.textContent = "Standard Flat Rates";
    if (quoteBreakdownContainer) quoteBreakdownContainer.classList.add("hidden");
    activeQuote = null;
    return;
  }

  try {
    const ratePlanCode = bookingRatePlan ? bookingRatePlan.value : "BAR";
    const payload = {
      room_id: selectedRoomId,
      check_in_date: checkIn,
      check_out_date: checkOut,
      rate_plan_code: ratePlanCode,
      coupon_code: couponCode,
      amenity_ids: [],
    };

    const res = await fetch("/api/pricing/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      // Fallback
      const total = (nights * room.price_per_night).toFixed(2);
      rateCalculation.textContent = `$${room.price_per_night.toFixed(2)} × ${nights} night${nights > 1 ? "s" : ""}`;
      estimateTotal.textContent = `$${total}`;
      if (quoteBreakdownContainer) quoteBreakdownContainer.classList.add("hidden");
      return;
    }

    const quote = await res.json();
    activeQuote = quote;

    estimateTotal.textContent = `$${quote.grand_total.toFixed(2)}`;
    const avgNightly = (quote.raw_room_total / quote.nights).toFixed(2);
    rateCalculation.textContent = `$${avgNightly} avg/night • ${quote.nights} night${quote.nights > 1 ? "s" : ""}`;

    if (pricingEngineStatus) {
      if (quote.min_los_met === false) {
        pricingEngineStatus.textContent = `⚠️ Min ${quote.min_los_required} Nights Required`;
      } else if (quote.coupon_applied) {
        pricingEngineStatus.textContent = `Promo ${quote.coupon_code} (-$${quote.coupon_discount.toFixed(2)})`;
      } else if (quote.occupancy_surge_total > 0) {
        pricingEngineStatus.textContent = `Demand Yield Surge (+${quote.occupancy_rate}% Occ)`;
      } else if (quote.weekend_surge_total > 0) {
        pricingEngineStatus.textContent = "Weekend Dynamic Surge";
      } else {
        pricingEngineStatus.textContent = `${quote.rate_plan_name || "Smart Dynamic Pricing"}`;
      }
    }

    renderQuoteBreakdown(quote);
  } catch (err) {
    console.warn("Quote fetch error:", err);
  }
}

function renderQuoteBreakdown(quote) {
  if (!quoteBreakdownContainer) return;
  quoteBreakdownContainer.classList.remove("hidden");

  let html = `
    <div class="quote-line">
      <span>Base Accommodation (${quote.nights} night${quote.nights > 1 ? "s" : ""})</span>
      <span>$${quote.raw_room_total.toFixed(2)}</span>
    </div>
  `;

  if (quote.rate_plan_adjustment && quote.rate_plan_adjustment !== 0) {
    const isDiscount = quote.rate_plan_adjustment < 0;
    html += `
      <div class="quote-line ${isDiscount ? 'quote-discount' : 'quote-surge'}">
        <span>Rate Plan (${escapeHtml(quote.rate_plan_code)}) ${isDiscount ? 'Savings' : 'Package Surcharge'}</span>
        <span>${isDiscount ? '-' : '+'}$${Math.abs(quote.rate_plan_adjustment).toFixed(2)}</span>
      </div>
    `;
  }

  if (quote.weekend_surge_total > 0) {
    html += `
      <div class="quote-line quote-surge">
        <span>Weekend Surge (+20% Fri/Sat)</span>
        <span>+$${quote.weekend_surge_total.toFixed(2)}</span>
      </div>
    `;
  }

  if (quote.seasonal_surge_total > 0) {
    html += `
      <div class="quote-line quote-surge">
        <span>High-Season Summer Surge (+15%)</span>
        <span>+$${quote.seasonal_surge_total.toFixed(2)}</span>
      </div>
    `;
  }

  if (quote.occupancy_surge_total > 0) {
    html += `
      <div class="quote-line quote-surge">
        <span>Occupancy Yield Surge (${quote.occupancy_rate}% Property Occ)</span>
        <span>+$${quote.occupancy_surge_total.toFixed(2)}</span>
      </div>
    `;
  }

  if (quote.length_of_stay_discount > 0) {
    html += `
      <div class="quote-line quote-discount">
        <span>Length-of-Stay Savings (Extended Stay)</span>
        <span>-$${quote.length_of_stay_discount.toFixed(2)}</span>
      </div>
    `;
  }

  if (quote.vip_discount > 0) {
    html += `
      <div class="quote-line quote-discount">
        <span>VIP Loyalty Benefit</span>
        <span>-$${quote.vip_discount.toFixed(2)}</span>
      </div>
    `;
  }

  if (quote.coupon_applied && quote.coupon_discount > 0) {
    html += `
      <div class="quote-line quote-discount">
        <span>Promotional Voucher (${quote.coupon_code})</span>
        <span>-$${quote.coupon_discount.toFixed(2)}</span>
      </div>
    `;
  }

  html += `
    <div class="quote-line">
      <span>Occupancy Tax (10%)</span>
      <span>+$${quote.tax_amount.toFixed(2)}</span>
    </div>
    <div class="quote-line quote-total-line">
      <span>Estimated Net Folio</span>
      <span style="color: #6ee7b7; font-weight: 700;">$${quote.grand_total.toFixed(2)}</span>
    </div>
  `;

  if (quote.min_los_met === false) {
    html += `
      <div class="quote-mlos-warning">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>${escapeHtml(quote.rate_plan_name)} requires a minimum stay of ${quote.min_los_required} nights. (Requested: ${quote.nights} night${quote.nights > 1 ? 's' : ''})</span>
      </div>
    `;
  }

  quoteBreakdownContainer.innerHTML = html;
}

/**
 * Validates promo coupon via POST /coupons/validate and updates UI
 */
async function handleApplyCoupon() {
  if (!couponCodeInput) return;
  const code = couponCodeInput.value.trim().toUpperCase();
  if (!code) {
    showToast("Please enter a coupon code.", "error");
    return;
  }

  const room = allRoomsData.find((r) => r.id === selectedRoomId);
  const checkIn = bookingCheckIn.value;
  const checkOut = bookingCheckOut.value;
  let estimatedAmount = 100.0;
  if (room && checkIn && checkOut) {
    const d1 = new Date(checkIn);
    const d2 = new Date(checkOut);
    const nights = Math.max(1, Math.ceil((d2.getTime() - d1.getTime()) / (1000 * 60 * 60 * 24)));
    estimatedAmount = nights * room.price_per_night;
  }

  try {
    const res = await fetch("/api/coupons/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code, total_amount: estimatedAmount }),
    });
    const data = await res.json();
    if (couponStatusMessage) {
      couponStatusMessage.classList.remove("hidden");
      if (data.is_valid) {
        couponStatusMessage.className = "coupon-status-msg valid";
        couponStatusMessage.textContent = `✓ ${data.message}`;
        showToast(`Coupon "${code}" validated!`, "success");
      } else {
        couponStatusMessage.className = "coupon-status-msg invalid";
        couponStatusMessage.textContent = `✗ ${data.message}`;
        showToast(data.message, "error");
      }
    }
    updateCostEstimate();
  } catch (err) {
    showToast(`Coupon validation failed: ${err.message}`, "error");
  }
}

// ==========================================
// 6. Reservation Submission
// ==========================================

async function handleBookingSubmit(event) {
  event.preventDefault();

  if (!selectedRoomId) {
    showToast("Please select an available room from the catalog.", "error");
    return;
  }

  const checkIn = bookingCheckIn.value;
  const checkOut = bookingCheckOut.value;
  const firstName = guestFirstName.value.trim();
  const lastName = guestLastName.value.trim();
  const email = guestEmail.value.trim();
  const phone = guestPhone.value.trim();

  if (!checkIn || !checkOut || !firstName || !lastName || !email || !phone) {
    showToast("Please fill in all required guest and date fields.", "error");
    return;
  }

  if (checkOut <= checkIn) {
    showToast("Check-out date must be strictly after check-in date.", "error");
    return;
  }

  const ratePlan = bookingRatePlan ? bookingRatePlan.value : "BAR";
  const couponCode = couponCodeInput && couponCodeInput.value.trim() ? couponCodeInput.value.trim().toUpperCase() : null;
  const applyDynamic = toggleDynamicPricing ? toggleDynamicPricing.checked : false;

  const payload = {
    room_id: selectedRoomId,
    check_in_date: checkIn,
    check_out_date: checkOut,
    rate_plan_code: ratePlan,
    adults: bookingAdults ? parseInt(bookingAdults.value || 1, 10) : 1,
    children: bookingChildren ? parseInt(bookingChildren.value || 0, 10) : 0,
    estimated_arrival_time: bookingETA ? (bookingETA.value || "15:00") : "15:00",
    guarantee_type: bookingGuarantee ? bookingGuarantee.value : "Guaranteed",
    early_checkin_requested: bookingEarlyCheckin ? bookingEarlyCheckin.checked : false,
    late_checkout_requested: bookingLateCheckout ? bookingLateCheckout.checked : false,
    special_requests: bookingSpecialRequests ? bookingSpecialRequests.value.trim() : "",
    guest: {
      first_name: firstName,
      last_name: lastName,
      email: email,
      phone: phone,
    },
    coupon_code: couponCode,
    apply_dynamic_pricing: applyDynamic,
  };

  setSubmitting(true);

  try {
    const response = await fetch("/api/bookings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
      showToast(data.detail || `Server error: HTTP ${response.status}`, "error");
      return;
    }

    // Success! Show receipt modal and refresh stats & rooms & front desk table
    showBookingReceipt(data);
    showToast("Reservation Confirmed.", "success");
    guestFirstName.value = "";
    guestLastName.value = "";
    guestEmail.value = "";
    guestPhone.value = "";
    if (bookingSpecialRequests) bookingSpecialRequests.value = "";
    if (bookingEarlyCheckin) bookingEarlyCheckin.checked = false;
    if (bookingLateCheckout) bookingLateCheckout.checked = false;
    if (autoAssignBadge) autoAssignBadge.classList.add("hidden");
    if (couponCodeInput) couponCodeInput.value = "";
    if (couponStatusMessage) couponStatusMessage.classList.add("hidden");
    fetchKPIs();
    fetchRooms();
    fetchBookings();
    fetchAuditLogs();
  } catch (err) {
    console.error("Booking error:", err);
    showToast(`Network error: ${err.message}`, "error");
  } finally {
    setSubmitting(false);
  }
}

function showBookingReceipt(booking) {
  let discountHtml = "";
  if (booking.coupon_code && booking.discount_amount > 0) {
    discountHtml = `
      <div class="receipt-row" style="color: #6ee7b7;">
        <span class="receipt-label">Promo Coupon (${booking.coupon_code})</span>
        <span class="receipt-value">-$${booking.discount_amount.toFixed(2)}</span>
      </div>
    `;
  }

  const pCode = booking.rate_plan_code || "BAR";
  const pClass = pCode === "NON_REF" ? "plan-pill-saver" : (pCode === "BB_PACKAGE" ? "plan-pill-bb" : (pCode === "CORP_EXTENDED" ? "plan-pill-corp" : "plan-pill-bar"));

  const adults = booking.adults || 1;
  const children = booking.children || 0;
  const partyText = `${adults} Adult${adults > 1 ? 's' : ''}${children > 0 ? ` + ${children} Child${children > 1 ? 'ren' : ''}` : ''}`;
  const guarantee = booking.guarantee_type || "Guaranteed";
  const eta = booking.estimated_arrival_time || "15:00";
  const scheduleRequests = [];
  if (booking.early_checkin_requested) scheduleRequests.push("Early Check-in");
  if (booking.late_checkout_requested) scheduleRequests.push("Late Check-out");
  const scheduleHtml = scheduleRequests.length > 0 ? `
    <div class="receipt-row">
      <span class="receipt-label">Schedule Requests</span>
      <span class="receipt-value">${scheduleRequests.join(" • ")}</span>
    </div>
  ` : "";

  const specialReqHtml = booking.special_requests ? `
    <div class="receipt-row">
      <span class="receipt-label">Special Requests</span>
      <span class="receipt-value" style="font-style: italic;">${escapeHtml(booking.special_requests)}</span>
    </div>
  ` : "";

  modalDetails.innerHTML = `
    <div class="receipt-grid">
      <div class="receipt-row">
        <span class="receipt-label">Confirmation ID</span>
        <span class="receipt-value">#${booking.id}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Status</span>
        <span class="receipt-value" style="color: var(--status-available-text);">${booking.booking_status}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Rate Plan</span>
        <span class="receipt-value"><span class="booking-plan-pill ${pClass}">${pCode}</span></span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Guarantee Policy</span>
        <span class="receipt-value"><span class="booking-guarantee-pill ${guarantee === 'Guaranteed' ? 'guarantee-firm' : 'guarantee-tentative'}">${guarantee}</span></span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Room</span>
        <span class="receipt-value">Room ${booking.room ? booking.room.room_number : booking.room_id} (${booking.room ? booking.room.room_type : ""})</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Guest</span>
        <span class="receipt-value">${booking.guest ? booking.guest.first_name + " " + booking.guest.last_name : "Guest #" + booking.guest_id}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Party Headcount</span>
        <span class="receipt-value">${partyText}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Dates & ETA</span>
        <span class="receipt-value">${booking.check_in_date} to ${booking.check_out_date} (ETA: ${eta})</span>
      </div>
      ${scheduleHtml}
      ${specialReqHtml}
      ${discountHtml}
      <div class="receipt-row receipt-total">
        <span class="receipt-label">Total Amount</span>
        <span class="receipt-value">$${booking.total_price.toFixed(2)}</span>
      </div>
    </div>
  `;
  receiptModal.classList.remove("hidden");
}

function setLoading(isLoading) {
  if (loadingState) loadingState.classList.toggle("hidden", !isLoading);
  if (isLoading && roomsGrid && (!allRoomsData || allRoomsData.length === 0)) {
    renderSkeletons();
  }
}

function renderSkeletons() {
  if (!roomsGrid) return;
  roomsGrid.setAttribute("aria-busy", "true");
  roomsGrid.innerHTML = Array(6).fill(0).map(() => `
    <div class="room-skeleton-card" aria-hidden="true">
      <div class="skeleton-header">
        <div class="skeleton skeleton-badge"></div>
        <div class="skeleton skeleton-pill"></div>
      </div>
      <div class="skeleton skeleton-title"></div>
      <div class="skeleton skeleton-price"></div>
      <div class="skeleton skeleton-btn"></div>
    </div>
  `).join('');
}

function setSubmitting(isSubmitting) {
  submitBookingBtn.disabled = isSubmitting;
  btnText.textContent = isSubmitting ? "Processing..." : "Confirm Reservation";
  btnSpinner.classList.toggle("hidden", !isSubmitting);
}

function showToast(message, type = "info") {
  if (!toastContainer) return;
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;

  let iconSvg = '';
  if (type === "success") {
    iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--status-available-text); flex-shrink: 0; margin-top: 1px;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
  } else if (type === "error") {
    iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--status-error-text); flex-shrink: 0; margin-top: 1px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
  } else {
    iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--brand-primary); flex-shrink: 0; margin-top: 1px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
  }

  toast.innerHTML = `
    ${iconSvg}
    <div style="flex: 1; font-weight: 500; line-height: 1.4;">${message}</div>
  `;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    toast.style.transition = "all 0.25s ease";
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

// ==========================================
// 7. Front Desk & Reservations Lifecycle Engine
// ==========================================

let currentBookingsData = [];

async function fetchBookings(statusFilter = "") {
  if (!reservationsTableBody) return;

  try {
    const url = statusFilter ? `/api/bookings?status=${encodeURIComponent(statusFilter)}` : "/api/bookings";
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    currentBookingsData = await response.json();
    renderBookings(currentBookingsData);
  } catch (err) {
    console.error("Failed to fetch reservations:", err);
    reservationsTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">Failed to load reservations.</td></tr>`;
  }
}

function renderBookings(bookings) {
  if (!reservationsTableBody) return;
  reservationsTableBody.innerHTML = "";

  if (!bookings || bookings.length === 0) {
    reservationsEmpty.classList.remove("hidden");
    return;
  }
  reservationsEmpty.classList.add("hidden");

  bookings.forEach((b) => {
    const tr = document.createElement("tr");

    // Status pill
    let statusClass = "status-pill-available";
    if (b.booking_status === "Checked-in") statusClass = "status-pill-occupied";
    else if (b.booking_status === "Checked-out") statusClass = "status-pill-cleaning";
    else if (b.booking_status === "Cancelled") statusClass = "status-pill-maintenance";

    // Lifecycle actions
    let actionButtons = `
      <div class="table-actions-group">
        <button type="button" class="btn btn-table-action btn-view-folio" onclick="openFolioModal(${b.id})" title="View itemized folio & incidentals">Folio</button>
    `;
    if (b.booking_status === "Confirmed") {
      actionButtons += `
        <button type="button" class="btn btn-table-action btn-checkin" onclick="handleCheckIn(${b.id})">Check In</button>
        <button type="button" class="btn btn-table-action btn-cancel" onclick="handleCancel(${b.id})">Cancel</button>
      `;
    } else if (b.booking_status === "Checked-in") {
      actionButtons += `
        <button type="button" class="btn btn-table-action btn-checkout" onclick="handleCheckOut(${b.id})">Check Out</button>
      `;
    } else if (b.booking_status === "Checked-out") {
      actionButtons += `<span style="font-size: 11px; color: var(--text-muted); align-self: center;">Completed</span>`;
    } else if (b.booking_status === "Cancelled") {
      actionButtons += `<span style="font-size: 11px; color: #fda4af; align-self: center;">Cancelled</span>`;
    }
    actionButtons += `</div>`;

    const guestName = b.guest ? `${escapeHtml(b.guest.first_name)} ${escapeHtml(b.guest.last_name)}` : `Guest #${b.guest_id}`;
    const guestContact = b.guest ? (escapeHtml(b.guest.email || b.guest.phone || "")) : "";
    const roomNumber = b.room ? b.room.room_number : b.room_id;
    const roomType = b.room ? b.room.room_type : "";

    const adults = b.adults || 1;
    const children = b.children || 0;
    const partyBadge = `<span class="booking-headcount-badge" title="Party: ${adults} Adults, ${children} Children">👥 ${adults}A${children > 0 ? `+${children}C` : ''}</span>`;
    const guarantee = b.guarantee_type || "Guaranteed";
    const guaranteeBadge = `<span class="booking-guarantee-pill ${guarantee === 'Guaranteed' ? 'guarantee-firm' : 'guarantee-tentative'}">${escapeHtml(guarantee)}</span>`;
    
    let etaDetail = `🕒 ETA ${escapeHtml(b.estimated_arrival_time || '15:00')}`;
    if (b.early_checkin_requested) etaDetail += ` • Early`;
    if (b.late_checkout_requested) etaDetail += ` • Late`;
    const etaText = `<span class="booking-eta-sub">${etaDetail}</span>`;

    const specialRequestSnippet = b.special_requests ? `<div class="booking-special-req-snippet" title="${escapeHtml(b.special_requests)}">📝 ${escapeHtml(b.special_requests.length > 25 ? b.special_requests.slice(0, 25) + '...' : b.special_requests)}</div>` : '';

    const planCode = b.rate_plan_code || "BAR";
    const planClass = planCode === "NON_REF" ? "plan-pill-saver" : (planCode === "BB_PACKAGE" ? "plan-pill-bb" : (planCode === "CORP_EXTENDED" ? "plan-pill-corp" : "plan-pill-bar"));
    const ratePlanPill = `<span class="booking-plan-pill ${planClass}" title="Rate Plan: ${escapeHtml(planCode)}">${escapeHtml(planCode)}</span>`;

    tr.innerHTML = `
      <td><span class="table-folio-id">#${b.id}</span></td>
      <td>
        <div class="table-guest-meta">
          <div><span class="table-guest-name">${guestName}</span> ${guaranteeBadge}</div>
          <span class="table-guest-contact">${guestContact}</span>
          <div>${partyBadge} ${ratePlanPill}</div>
          ${specialRequestSnippet}
        </div>
      </td>
      <td>
        <div class="table-room-meta">
          <strong>Room ${roomNumber}</strong>
          <span style="font-size: 11px; color: var(--text-muted);">(${roomType})</span>
        </div>
      </td>
      <td>
        <div class="table-dates-meta">
          <span>${b.check_in_date} → ${b.check_out_date}</span>
          ${etaText}
        </div>
      </td>
      <td><span class="table-price">$${b.total_price.toFixed(2)}</span></td>
      <td><span class="status-pill ${statusClass}">${b.booking_status}</span></td>
      <td>${actionButtons}</td>
    `;

    reservationsTableBody.appendChild(tr);
  });
}

/**
 * Handles guest arrival check-in via POST /bookings/{id}/check-in
 */
async function handleCheckIn(bookingId) {
  try {
    const res = await fetch(`/api/bookings/${bookingId}/check-in`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    showToast(`Folio #${bookingId} checked in. Room marked as Occupied.`, "success");
    fetchBookings();
    fetchRooms();
    fetchKPIs();
    fetchAuditLogs();
    fetchHousekeepingDashboard();
    fetchHousekeepingTasks(currentHkFilter);
    fetchSecurityDashboard();
    fetchKeycards();
  } catch (err) {
    showToast(`Check-in failed: ${err.message}`, "error");
  }
}

/**
 * Handles guest checkout via POST /bookings/{id}/check-out
 * Generates transparent invoice folio statement
 */
async function handleCheckOut(bookingId) {
  try {
    const res = await fetch(`/api/bookings/${bookingId}/check-out`, { method: "POST" });
    const folio = await res.json();
    if (!res.ok) throw new Error(folio.detail || `HTTP ${res.status}`);

    showInvoiceFolio(folio);
    showToast(`Folio #${bookingId} checked out. Room dispatched to Housekeeping.`, "success");
    fetchBookings();
    fetchRooms();
    fetchKPIs();
    fetchAuditLogs();
    fetchHousekeepingDashboard();
    fetchHousekeepingTasks(currentHkFilter);
    fetchSecurityDashboard();
    fetchKeycards();
  } catch (err) {
    showToast(`Check-out failed: ${err.message}`, "error");
  }
}

/**
 * Handles reservation cancellation via POST /bookings/{id}/cancel
 */
async function handleCancel(bookingId) {
  if (!confirm(`Are you sure you want to cancel reservation #${bookingId}?`)) return;

  try {
    const res = await fetch(`/api/bookings/${bookingId}/cancel`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    showToast(`Folio #${bookingId} cancelled. Refund: $${data.refund_amount.toFixed(2)}.`, "info");
    fetchBookings();
    fetchRooms();
    fetchKPIs();
    fetchAuditLogs();
  } catch (err) {
    showToast(`Cancellation failed: ${err.message}`, "error");
  }
}

/**
 * Displays itemized checkout invoice folio in wide modal
 */
function showInvoiceFolio(folio) {
  invoiceSubtitle.textContent = `Folio #${folio.booking_id} • ${folio.guest_name} • ${folio.checkout_timestamp}`;

  let itemsHtml = folio.invoice_breakdown
    .map(
      (item) => `
      <tr>
        <td>${item.description}</td>
        <td style="text-align: center;">${item.quantity}</td>
        <td style="text-align: right;">$${item.unit_price.toFixed(2)}</td>
        <td style="text-align: right; font-weight: 600;">$${item.total_amount.toFixed(2)}</td>
      </tr>
    `
    )
    .join("");

  invoiceDetails.innerHTML = `
    <div class="receipt-grid" style="margin-bottom: 16px;">
      <div class="receipt-row">
        <span class="receipt-label">Guest</span>
        <span class="receipt-value">${folio.guest_name} (${folio.guest_email})</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Accommodation</span>
        <span class="receipt-value">Room ${folio.room_number} • ${folio.room_type} (${folio.nights} nights)</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Stay Period</span>
        <span class="receipt-value">${folio.check_in_date} to ${folio.check_out_date}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Room Housekeeping Status</span>
        <span class="receipt-value" style="color: var(--status-cleaning-text); font-weight: 700;">${folio.room_status_after_checkout} (Sanitization Triggered)</span>
      </div>
    </div>

    <table class="invoice-table">
      <thead>
        <tr>
          <th>Description</th>
          <th style="text-align: center;">Qty</th>
          <th style="text-align: right;">Unit Rate</th>
          <th style="text-align: right;">Amount</th>
        </tr>
      </thead>
      <tbody>
        ${itemsHtml}
      </tbody>
    </table>

    <div class="receipt-grid" style="border-top: 1px solid var(--border-subtle); padding-top: 12px;">
      <div class="receipt-row">
        <span class="receipt-label">Subtotal</span>
        <span class="receipt-value">$${(folio.base_room_charge + folio.amenities_charge).toFixed(2)}</span>
      </div>
      <div class="receipt-row">
        <span class="receipt-label">Occupancy Tax (10%)</span>
        <span class="receipt-value">$${folio.tax_amount.toFixed(2)}</span>
      </div>
      <div class="receipt-row receipt-total">
        <span class="receipt-label" style="font-size: 15px; font-weight: 700;">Grand Total Folio</span>
        <span class="receipt-value" style="font-size: 18px; color: #6ee7b7;">$${folio.grand_total.toFixed(2)}</span>
      </div>
    </div>
  `;

  invoiceModal.classList.remove("hidden");
}

// ==========================================
// 8. Module 10: Guest CRM & Loyalty Hub
// ==========================================

let currentGuestsData = [];

/**
 * Fetches guests from GET /guests with optional query and VIP tier filter
 */
async function fetchGuests(q = "", tier = "") {
  if (!guestsTableBody) return;

  try {
    const params = new URLSearchParams();
    if (q && q.trim()) params.append("q", q.trim());
    if (tier) params.append("vip_tier", tier);

    const queryString = params.toString();
    const url = queryString ? `/api/guests?${queryString}` : "/api/guests";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    currentGuestsData = await res.json();
    renderGuests(currentGuestsData);
  } catch (err) {
    console.error("Failed to load guests:", err);
    guestsTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">Failed to load guest directory.</td></tr>`;
  }
}

/**
 * Renders guest CRM list in the dashboard table
 */
function renderGuests(guests) {
  if (!guestsTableBody) return;
  guestsTableBody.innerHTML = "";

  if (!guests || guests.length === 0) {
    guestsEmpty.classList.remove("hidden");
    return;
  }
  guestsEmpty.classList.add("hidden");

  guests.forEach((g) => {
    const tr = document.createElement("tr");

    // Initials for avatar
    const initials = `${g.first_name[0] || ""}${g.last_name[0] || ""}`.toUpperCase();

    // Tier badge class
    let tierClass = "tier-standard";
    if (g.vip_tier === "Silver") tierClass = "tier-silver";
    if (g.vip_tier === "Gold") tierClass = "tier-gold";
    if (g.vip_tier === "Platinum") tierClass = "tier-platinum";

    const notesPreview = g.notes ? g.notes : `<span style="color: rgba(255,255,255,0.25); font-style: italic;">No preferences recorded</span>`;

    tr.innerHTML = `
      <td>
        <div class="guest-avatar-group">
          <div class="guest-avatar">${initials}</div>
          <div>
            <strong>${g.first_name} ${g.last_name}</strong>
            <div style="font-size: 11px; color: var(--text-muted);">ID #${g.id}</div>
          </div>
        </div>
      </td>
      <td>
        <div style="font-size: 12px; font-weight: 500;">${g.email}</div>
        <div style="font-size: 11px; color: var(--text-muted);">${g.phone}</div>
      </td>
      <td>
        <span class="tier-badge ${tierClass}">★ ${g.vip_tier}</span>
      </td>
      <td>
        <div style="font-size: 13px; font-weight: 600;">${g.completed_stays} / ${g.total_bookings}</div>
        <div style="font-size: 10px; color: var(--text-muted);">${g.active_stays} active now</div>
      </td>
      <td>
        <div style="font-size: 13px; font-weight: 700; color: #6ee7b7;">$${g.lifetime_spent.toFixed(2)}</div>
        <div style="font-size: 10px; color: var(--text-muted);">Avg: $${g.average_spend_per_stay.toFixed(2)}/stay</div>
      </td>
      <td>
        <div class="guest-notes-preview" title="${g.notes || ''}">${notesPreview}</div>
      </td>
      <td>
        <button type="button" class="btn btn-table-action btn-checkout" onclick="openGuestDetail(${g.id})">
          View Folio & CRM
        </button>
      </td>
    `;
    guestsTableBody.appendChild(tr);
  });
}

/**
 * Opens detailed guest profile with editable CRM fields and stay history
 */
async function openGuestDetail(guestId) {
  try {
    const res = await fetch(`/api/guests/${guestId}`);
    if (!res.ok) throw new Error("Could not fetch guest details");
    const detail = await res.json();

    const titleEl = document.getElementById("guestDetailModalTitle");
    const subEl = document.getElementById("guestDetailModalSubtitle");
    if (titleEl) titleEl.textContent = `${detail.first_name} ${detail.last_name}`;
    if (subEl) subEl.textContent = `${detail.email} • ${detail.phone} • Enrolled ${detail.created_at ? detail.created_at.split('T')[0] : 'Member'}`;

    // Stay history rows
    let historyRows = "";
    if (detail.stay_history && detail.stay_history.length > 0) {
      historyRows = detail.stay_history
        .map((b) => {
          let statusStyle = "color: #6ee7b7;";
          if (b.booking_status === "Checked-in") statusStyle = "color: #93c5fd;";
          if (b.booking_status === "Cancelled") statusStyle = "color: #fda4af;";

          const roomStr = b.room ? `Room ${b.room.room_number} (${b.room.room_type})` : `Room #${b.room_id}`;
          return `
            <tr>
              <td><strong>#${b.id}</strong></td>
              <td>${roomStr}</td>
              <td>${b.check_in_date} → ${b.check_out_date}</td>
              <td style="font-weight: 600;">$${b.total_price.toFixed(2)}</td>
              <td style="${statusStyle}; font-weight: 600;">${b.booking_status}</td>
            </tr>
          `;
        })
        .join("");
    } else {
      historyRows = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 16px;">No reservation stays on record.</td></tr>`;
    }

    guestDetailBody.innerHTML = `
      <div class="receipt-grid" style="margin-bottom: 20px;">
        <div class="receipt-row">
          <span class="receipt-label">Lifetime Spend</span>
          <span class="receipt-value" style="font-size: 15px; color: #6ee7b7; font-weight: 700;">$${detail.lifetime_spent.toFixed(2)}</span>
        </div>
        <div class="receipt-row">
          <span class="receipt-label">Completed Stays</span>
          <span class="receipt-value">${detail.completed_stays} Completed (${detail.total_bookings} Total)</span>
        </div>
        <div class="receipt-row">
          <span class="receipt-label">Average Spend</span>
          <span class="receipt-value">$${detail.average_spend_per_stay.toFixed(2)} per stay</span>
        </div>
        <div class="receipt-row">
          <span class="receipt-label">Last Stay Date</span>
          <span class="receipt-value">${detail.last_stay_date || 'No completed stays'}</span>
        </div>
      </div>

      <div style="background-color: var(--canvas-bg); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 16px; margin-bottom: 20px;">
        <h4 style="margin: 0 0 12px; font-size: 13px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.04em;">VIP Loyalty Tier & Preferences</h4>
        
        <div class="form-row" style="margin-bottom: 12px;">
          <div class="form-control">
            <label for="modalEditTier" style="font-size: 11px;">VIP Loyalty Classification</label>
            <select id="modalEditTier" class="form-select" style="font-size: 12px;">
              <option value="Standard" ${detail.vip_tier === "Standard" ? "selected" : ""}>Standard Tier</option>
              <option value="Silver" ${detail.vip_tier === "Silver" ? "selected" : ""}>Silver (VIP)</option>
              <option value="Gold" ${detail.vip_tier === "Gold" ? "selected" : ""}>Gold (VIP Elite)</option>
              <option value="Platinum" ${detail.vip_tier === "Platinum" ? "selected" : ""}>Platinum (Presidential)</option>
            </select>
          </div>
        </div>

        <div class="form-control" style="margin-bottom: 12px;">
          <label for="modalEditNotes" style="font-size: 11px;">Guest Preferences & Internal Notes</label>
          <textarea id="modalEditNotes" rows="2" class="form-textarea" placeholder="E.g., Prefers corner room, hypoallergenic bedding, late checkout...">${detail.notes || ""}</textarea>
        </div>

        <button type="button" class="btn btn-primary" onclick="saveGuestCRM(${detail.id})" style="font-size: 12px; padding: 7px 16px;">
          Save CRM Updates
        </button>
      </div>

      <h4 style="margin: 0 0 8px; font-size: 13px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.04em;">Complete Stay & Folio History</h4>
      <div style="max-height: 180px; overflow-y: auto;">
        <table class="stay-history-table">
          <thead>
            <tr>
              <th>Folio #</th>
              <th>Room</th>
              <th>Dates</th>
              <th>Total</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${historyRows}
          </tbody>
        </table>
      </div>
    `;

    guestDetailModal.classList.remove("hidden");
  } catch (err) {
    showToast(`Failed to load guest folio: ${err.message}`, "error");
  }
}

/**
 * Updates guest VIP tier and notes via PATCH /guests/{id}
 */
async function saveGuestCRM(guestId) {
  const tierSelect = document.getElementById("modalEditTier");
  const notesArea = document.getElementById("modalEditNotes");

  const payload = {
    vip_tier: tierSelect.value,
    notes: notesArea.value.trim(),
  };

  try {
    const res = await fetch(`/api/guests/${guestId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: jsonSafeStringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    showToast("Guest CRM profile and preferences updated successfully.", "success");
    guestDetailModal.classList.add("hidden");
    const activeTier = guestTierTabs ? guestTierTabs.querySelector(".tab-btn.active")?.dataset.tier || "" : "";
    const q = guestSearchInput ? guestSearchInput.value : "";
    fetchGuests(q, activeTier);
    fetchAuditLogs();
  } catch (err) {
    showToast(`Error updating CRM: ${err.message}`, "error");
  }
}

/**
 * Creates new guest profile via POST /guests
 */
async function handleCreateNewGuest(e) {
  e.preventDefault();

  const firstName = document.getElementById("newGuestFirstName").value.trim();
  const lastName = document.getElementById("newGuestLastName").value.trim();
  const email = document.getElementById("newGuestEmail").value.trim();
  const phone = document.getElementById("newGuestPhone").value.trim();
  const vipTier = document.getElementById("newGuestTier").value;
  const notes = document.getElementById("newGuestNotes").value.trim();

  if (!firstName || !lastName || !email || !phone) {
    showToast("Please fill in all required guest fields.", "error");
    return;
  }

  const payload = {
    first_name: firstName,
    last_name: lastName,
    email: email,
    phone: phone,
    vip_tier: vipTier,
    notes: notes,
  };

  try {
    const res = await fetch("/api/guests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: jsonSafeStringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    showToast(`Guest profile for ${firstName} ${lastName} enrolled successfully!`, "success");
    newGuestModal.classList.add("hidden");
    fetchGuests();
    fetchAuditLogs();
  } catch (err) {
    showToast(`Enrollment failed: ${err.message}`, "error");
  }
}

function jsonSafeStringify(obj) {
  return JSON.stringify(obj);
}

// ==========================================
// 9. Module 12: Operations Audit Trail
// ==========================================

let currentAuditLogsData = [];

async function fetchAuditLogs(entityFilter = "") {
  if (!auditLogsTableBody) return;

  try {
    const url = entityFilter ? `/api/audit-logs?entity_type=${encodeURIComponent(entityFilter)}` : "/api/audit-logs";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    currentAuditLogsData = await res.json();
    renderAuditLogs(currentAuditLogsData);
  } catch (err) {
    console.error("Failed to fetch audit logs:", err);
    auditLogsTableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Failed to load audit trail.</td></tr>`;
  }
}

function renderAuditLogs(logs) {
  if (!auditLogsTableBody) return;
  auditLogsTableBody.innerHTML = "";

  if (!logs || logs.length === 0) {
    if (auditLogsEmpty) auditLogsEmpty.classList.remove("hidden");
    return;
  }
  if (auditLogsEmpty) auditLogsEmpty.classList.add("hidden");

  logs.forEach((log) => {
    const tr = document.createElement("tr");

    let actionClass = "action-system";
    if (log.entity_type === "Room") actionClass = "action-room";
    else if (log.entity_type === "Booking") actionClass = "action-booking";
    else if (log.entity_type === "Guest") actionClass = "action-guest";
    else if (log.entity_type === "Coupon") actionClass = "action-coupon";

    let targetLabel = log.entity_type;
    if (log.entity_id) targetLabel += ` #${log.entity_id}`;

    // Format details JSON nicely
    let detailsDisplay = log.details || "—";
    try {
      const parsed = JSON.parse(log.details);
      if (typeof parsed === "object" && parsed !== null) {
        detailsDisplay = Object.entries(parsed)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" • ");
      }
    } catch (_) {}

    tr.innerHTML = `
      <td><span class="table-folio-id">${formatTimestamp(log.timestamp)}</span></td>
      <td><span class="audit-action-badge ${actionClass}">${log.action}</span></td>
      <td><strong>${targetLabel}</strong></td>
      <td><span style="font-size: 12px; color: var(--text-high-contrast);">${log.actor}</span></td>
      <td><span class="audit-payload-json" title="${escapeHtml(log.details || '')}">${escapeHtml(detailsDisplay)}</span></td>
    `;
    auditLogsTableBody.appendChild(tr);
  });
}

function formatTimestamp(ts) {
  if (!ts) return "—";
  try {
    return ts.replace("T", " ").split(".")[0];
  } catch (_) {
    return ts;
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ==========================================
// 10. Module 13: Maintenance Work Orders
// ==========================================

let currentMaintenanceTickets = [];

function populateTicketRoomSelect() {
  if (!ticketRoomSelect) return;
  ticketRoomSelect.innerHTML = allRoomsData
    .map(
      (r) =>
        `<option value="${r.id}" ${r.id === selectedRoomId ? "selected" : ""}>Room ${r.room_number} (${r.room_type} - ${r.status})</option>`
    )
    .join("");
}

async function fetchMaintenanceSummary() {
  try {
    const res = await fetch("/api/maintenance/tickets/summary");
    if (!res.ok) return;
    const data = await res.json();
    if (mKpiOpen) mKpiOpen.textContent = data.open_tickets;
    if (mKpiProgress) mKpiProgress.textContent = data.in_progress_tickets;
    if (mKpiUrgent) mKpiUrgent.textContent = data.urgent_tickets;
    if (mKpiResolved) mKpiResolved.textContent = data.resolved_tickets;
  } catch (err) {
    console.warn("Failed to fetch maintenance summary:", err);
  }
}

async function fetchMaintenanceTickets(statusFilter = "") {
  if (!maintenanceTableBody) return;

  try {
    const url = statusFilter ? `/api/maintenance/tickets?status=${encodeURIComponent(statusFilter)}` : "/api/maintenance/tickets";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    currentMaintenanceTickets = await res.json();
    renderMaintenanceTickets(currentMaintenanceTickets);
  } catch (err) {
    console.error("Failed to fetch maintenance tickets:", err);
    maintenanceTableBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">Failed to load maintenance work orders.</td></tr>`;
  }
}

function renderMaintenanceTickets(tickets) {
  if (!maintenanceTableBody) return;
  maintenanceTableBody.innerHTML = "";

  if (!tickets || tickets.length === 0) {
    if (maintenanceEmpty) maintenanceEmpty.classList.remove("hidden");
    return;
  }
  if (maintenanceEmpty) maintenanceEmpty.classList.add("hidden");

  tickets.forEach((t) => {
    const tr = document.createElement("tr");

    let priorityClass = "priority-medium";
    if (t.priority === "Urgent") priorityClass = "priority-urgent";
    else if (t.priority === "High") priorityClass = "priority-high";
    else if (t.priority === "Low") priorityClass = "priority-low";

    let statusPillClass = "status-pill-available";
    if (t.status === "In Progress") statusPillClass = "status-pill-occupied";
    else if (t.status === "Resolved") statusPillClass = "status-pill-cleaning";
    else if (t.status === "Cancelled") statusPillClass = "status-pill-maintenance";

    let actionBtns = "";
    if (t.status === "Open") {
      actionBtns = `
        <div class="table-actions-group">
          <button type="button" class="btn btn-table-action btn-start-work" onclick="startMaintenanceWork(${t.id})">Start Work</button>
          <button type="button" class="btn btn-table-action btn-resolve" onclick="openResolveModal(${t.id}, '${t.room_number}')">Resolve</button>
        </div>
      `;
    } else if (t.status === "In Progress") {
      actionBtns = `
        <div class="table-actions-group">
          <button type="button" class="btn btn-table-action btn-resolve" onclick="openResolveModal(${t.id}, '${t.room_number}')">Resolve & Clear</button>
        </div>
      `;
    } else {
      actionBtns = `<span style="font-size: 11px; color: var(--text-muted);">Completed</span>`;
    }

    tr.innerHTML = `
      <td><span class="table-folio-id">#WO-${t.id}</span></td>
      <td><strong>Room ${t.room_number || t.room_id}</strong></td>
      <td>
        <div style="font-size: 12px; font-weight: 500; color: var(--text-high-contrast);">${escapeHtml(t.issue_description)}</div>
        ${t.resolution_notes ? `<div style="font-size: 11px; color: #6ee7b7; margin-top: 2px;">✓ ${escapeHtml(t.resolution_notes)}</div>` : ''}
      </td>
      <td><span class="trade-pill">${t.category}</span></td>
      <td><span class="priority-pill ${priorityClass}">${t.priority}</span></td>
      <td><span style="font-size: 12px; color: var(--text-muted);">${t.assigned_staff || 'Unassigned'}</span></td>
      <td><span class="status-pill ${statusPillClass}">${t.status}</span></td>
      <td>${actionBtns}</td>
    `;
    maintenanceTableBody.appendChild(tr);
  });
}

async function startMaintenanceWork(ticketId) {
  try {
    const res = await fetch(`/api/maintenance/tickets/${ticketId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "In Progress" }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    showToast(`Work Order #WO-${ticketId} status changed to In Progress.`, "info");
    fetchMaintenanceTickets();
    fetchMaintenanceSummary();
    fetchAuditLogs();
  } catch (err) {
    showToast(`Failed to update ticket: ${err.message}`, "error");
  }
}

function openResolveModal(ticketId, roomNumber) {
  if (resolveTicketId) resolveTicketId.value = ticketId;
  if (resolveNotes) resolveNotes.value = "";
  if (resolveModalTitle) resolveModalTitle.textContent = `Complete & Clear Work Order #WO-${ticketId}`;
  if (resolveModalSubtitle) resolveModalSubtitle.textContent = `Room ${roomNumber} - Document resolution and return to service`;
  if (resolveTicketModal) resolveTicketModal.classList.remove("hidden");
}

async function handleSubmitResolveTicket(e) {
  e.preventDefault();
  const ticketId = resolveTicketId.value;
  const notes = resolveNotes.value.trim();
  const autoRelease = resolveAutoRelease ? resolveAutoRelease.checked : true;

  if (!notes) {
    showToast("Please provide resolution notes before closing the ticket.", "error");
    return;
  }

  try {
    const res = await fetch(`/api/maintenance/tickets/${ticketId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "Resolved",
        resolution_notes: notes,
        auto_release_room: autoRelease,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    showToast(`Work Order #WO-${ticketId} resolved successfully.`, "success");
    if (resolveTicketModal) resolveTicketModal.classList.add("hidden");
    fetchMaintenanceTickets();
    fetchMaintenanceSummary();
    fetchRooms();
    fetchKPIs();
    fetchAuditLogs();
  } catch (err) {
    showToast(`Failed to resolve ticket: ${err.message}`, "error");
  }
}

async function handleCreateMaintenanceTicket(e) {
  e.preventDefault();

  const roomId = parseInt(ticketRoomSelect.value, 10);
  const category = document.getElementById("ticketCategorySelect").value;
  const priority = document.getElementById("ticketPrioritySelect").value;
  const description = document.getElementById("ticketDescription").value.trim();
  const assignedStaff = document.getElementById("ticketAssignedStaff").value.trim();
  const reportedBy = document.getElementById("ticketReportedBy").value.trim();
  const estimatedCost = parseFloat(document.getElementById("ticketEstimatedCost").value) || 0.0;
  const autoLock = document.getElementById("ticketAutoLock") ? document.getElementById("ticketAutoLock").checked : true;

  if (!roomId || !description) {
    showToast("Please select a room and enter the defect description.", "error");
    return;
  }

  const payload = {
    room_id: roomId,
    issue_description: description,
    category: category,
    priority: priority,
    assigned_staff: assignedStaff || "Facilities Team",
    reported_by: reportedBy || "Housekeeping",
    estimated_cost: estimatedCost,
    auto_lock_room: autoLock,
  };

  try {
    const res = await fetch("/api/maintenance/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    showToast(`Work Order #WO-${data.id} dispatched!`, "success");
    if (newTicketModal) newTicketModal.classList.add("hidden");
    fetchMaintenanceTickets();
    fetchMaintenanceSummary();
    fetchRooms();
    fetchKPIs();
    fetchAuditLogs();
  } catch (err) {
    showToast(`Failed to dispatch work order: ${err.message}`, "error");
  }
}


// ==========================================
// Module 14: Guest Folio & Incidentals Billing Engine
// ==========================================

let currentFolioBookingId = null;

/**
 * Opens the Guest Folio modal for a specific booking and loads its statement
 */
async function openFolioModal(bookingId) {
  currentFolioBookingId = bookingId;
  const modal = document.getElementById("folioModal");
  if (!modal) return;
  modal.classList.remove("hidden");
  await fetchBookingFolio(bookingId);
}

/**
 * Fetches itemized folio statement from GET /bookings/{bookingId}/folio
 */
async function fetchBookingFolio(bookingId) {
  try {
    const res = await fetch(`/api/bookings/${bookingId}/folio`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const folio = await res.json();
    renderFolioStatement(folio);
  } catch (err) {
    showToast(`Failed to load folio: ${err.message}`, "error");
  }
}

/**
 * Renders the itemized folio statement, metrics, and incidentals ledger
 */
function renderFolioStatement(folio) {
  const titleEl = document.getElementById("folioModalTitle");
  const subEl = document.getElementById("folioModalSubtitle");
  if (titleEl) titleEl.textContent = `Folio #${folio.booking_id} — ${folio.guest_name}`;
  if (subEl) subEl.textContent = `Room ${folio.room_number} • Stay: ${folio.check_in_date} to ${folio.check_out_date}`;

  const badge = document.getElementById("folioStatusBadge");
  if (badge) {
    badge.textContent = folio.booking_status;
    badge.className = `status-badge ${
      folio.booking_status === "Checked-in"
        ? "status-occupied"
        : folio.booking_status === "Checked-out"
        ? "status-cleaning"
        : folio.booking_status === "Cancelled"
        ? "status-maintenance"
        : "status-available"
    }`;
  }

  const elRoom = document.getElementById("folioRoomBase");
  const elAmen = document.getElementById("folioAmenities");
  const elDisc = document.getElementById("folioDiscount");
  const elInc = document.getElementById("folioIncidentalsTotal");
  const elBal = document.getElementById("folioBalanceDue");

  if (elRoom) elRoom.textContent = `$${folio.room_base_charge.toFixed(2)}`;
  if (elAmen) elAmen.textContent = `$${folio.amenities_charge.toFixed(2)}`;
  if (elDisc) {
    elDisc.textContent = `-$${folio.discount_amount.toFixed(2)} ${
      folio.coupon_code ? `(${folio.coupon_code})` : ""
    }`;
  }
  if (elInc) elInc.textContent = `$${folio.incidentals_total.toFixed(2)}`;
  if (elBal) elBal.textContent = `$${folio.balance_due.toFixed(2)}`;

  const targetInput = document.getElementById("folioTargetBookingId");
  if (targetInput) targetInput.value = folio.booking_id;

  // Toggle charge posting section based on reservation lifecycle status
  const postContainer = document.getElementById("folioPostChargeContainer");
  if (postContainer) {
    if (folio.booking_status === "Cancelled" || folio.booking_status === "Checked-out") {
      postContainer.style.display = "none";
    } else {
      postContainer.style.display = "block";
    }
  }

  const tbody = document.getElementById("folioChargesTableBody");
  const emptyState = document.getElementById("folioEmptyState");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!folio.incidentals || folio.incidentals.length === 0) {
    if (emptyState) emptyState.classList.remove("hidden");
    return;
  }
  if (emptyState) emptyState.classList.add("hidden");

  folio.incidentals.forEach((c) => {
    const tr = document.createElement("tr");
    const catClass = `category-${c.service_category.toLowerCase()}`;
    const statusClass =
      c.status === "Billed"
        ? "status-billed"
        : c.status === "Paid"
        ? "status-paid"
        : "status-voided";

    let actionHtml = "—";
    if (c.status === "Billed") {
      actionHtml = `<button type="button" class="btn-void-charge" onclick="promptVoidCharge(${c.id}, '${c.description.replace(/'/g, "\\'")}', ${c.total_price})">Void</button>`;
    } else if (c.status === "Voided" && c.void_reason) {
      actionHtml = `<span style="font-size: 10px; color: var(--text-muted);" title="${c.void_reason}">Voided (${c.void_reason.substring(0, 16)}...)</span>`;
    }

    tr.innerHTML = `
      <td><span class="category-badge ${catClass}">${c.service_category}</span></td>
      <td>
        <span style="${c.status === 'Voided' ? 'text-decoration: line-through; color: var(--text-muted);' : ''}">${c.description}</span>
      </td>
      <td>$${c.unit_price.toFixed(2)}</td>
      <td>${c.quantity}</td>
      <td><strong style="${c.status === 'Voided' ? 'text-decoration: line-through; opacity: 0.6;' : ''}">$${c.total_price.toFixed(2)}</strong></td>
      <td><span class="${statusClass}">${c.status}</span></td>
      <td><span style="font-size: 11px; color: var(--text-muted);">${c.posted_by}</span></td>
      <td>${actionHtml}</td>
    `;
    tbody.appendChild(tr);
  });
}

/**
 * Handles posting an incidental charge via POST /bookings/{id}/charges
 */
async function handlePostFolioCharge(e) {
  e.preventDefault();
  const bookingId = document.getElementById("folioTargetBookingId").value;
  const cat = document.getElementById("chargeCategorySelect").value;
  const desc = document.getElementById("chargeDescInput").value.trim();
  const price = parseFloat(document.getElementById("chargePriceInput").value);
  const qty = parseInt(document.getElementById("chargeQtyInput").value, 10);

  if (!desc || isNaN(price) || price < 0 || isNaN(qty) || qty <= 0) {
    showToast("Please provide a valid description, price, and quantity.", "error");
    return;
  }

  try {
    const res = await fetch(`/api/bookings/${bookingId}/charges`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service_category: cat,
        description: desc,
        unit_price: price,
        quantity: qty,
        posted_by: "Front Desk Agent",
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    showToast(`Posted $${(price * qty).toFixed(2)} (${cat}) to Folio #${bookingId}!`, "success");
    document.getElementById("chargeDescInput").value = "";
    document.getElementById("chargePriceInput").value = "";
    document.getElementById("chargeQtyInput").value = "1";
    await fetchBookingFolio(bookingId);
    fetchAuditLogs();
    fetchBookings();
  } catch (err) {
    showToast(`Failed to post charge: ${err.message}`, "error");
  }
}

/**
 * Prompts duty manager for audit justification to void a charge
 */
async function promptVoidCharge(chargeId, desc, amount) {
  const reason = prompt(`Provide audit justification for voiding "${desc}" ($${amount.toFixed(2)}):`, "Clerical error / disputed charge");
  if (!reason || !reason.trim()) return;

  try {
    const res = await fetch(`/api/folio-charges/${chargeId}/void`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ void_reason: reason.trim() }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    showToast(`Charge #${chargeId} successfully voided.`, "info");
    if (currentFolioBookingId) {
      await fetchBookingFolio(currentFolioBookingId);
    }
    fetchAuditLogs();
    fetchBookings();
  } catch (err) {
    showToast(`Failed to void charge: ${err.message}`, "error");
  }
}

// ==========================================
// Module 4: Housekeeping & Room Status Controller
// ==========================================

let currentHkFilter = "";

/**
 * Fetches executive housekeeping dashboard summary KPIs
 */
async function fetchHousekeepingDashboard() {
  try {
    const res = await fetch("/api/housekeeping/dashboard");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const elInspected = document.getElementById("hkKpiInspected");
    const elClean = document.getElementById("hkKpiClean");
    const elDirty = document.getElementById("hkKpiDirty");
    const elCleaning = document.getElementById("hkKpiCleaning");
    const elUrgent = document.getElementById("hkKpiUrgent");
    const elDnd = document.getElementById("hkKpiDnd");

    if (elInspected) elInspected.textContent = data.inspected_ready;
    if (elClean) elClean.textContent = data.clean_pending_inspection;
    if (elDirty) elDirty.textContent = data.dirty_needs_turnover;
    if (elCleaning) elCleaning.textContent = data.cleaning_in_progress;
    if (elUrgent) elUrgent.textContent = data.urgent_priority_count;
    if (elDnd) elDnd.textContent = data.dnd_active;
  } catch (err) {
    console.error("fetchHousekeepingDashboard error:", err);
  }
}

/**
 * Fetches housekeeping tasks catalog with optional status filter
 */
async function fetchHousekeepingTasks(statusFilter = "") {
  try {
    currentHkFilter = statusFilter;
    const url = statusFilter ? `/api/housekeeping/tasks?status=${encodeURIComponent(statusFilter)}` : "/api/housekeeping/tasks";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const tasks = await res.json();
    renderHousekeepingTable(tasks);
  } catch (err) {
    console.error("fetchHousekeepingTasks error:", err);
  }
}

/**
 * Renders housekeeping tasks in the dashboard table
 */
function renderHousekeepingTable(tasks) {
  const tbody = document.getElementById("housekeepingTableBody");
  const emptyPlaceholder = document.getElementById("housekeepingEmpty");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!tasks || tasks.length === 0) {
    if (emptyPlaceholder) emptyPlaceholder.classList.remove("hidden");
    return;
  }
  if (emptyPlaceholder) emptyPlaceholder.classList.add("hidden");

  tasks.forEach((t) => {
    const tr = document.createElement("tr");

    let priorityClass = "normal";
    if (t.priority === "High") priorityClass = "high";
    else if (t.priority === "Urgent VIP Arrival") priorityClass = "urgent";
    else if (t.priority === "Rush Checkout Turnover") priorityClass = "rush";

    const statusKey = (t.status || "").toLowerCase().replace(/[^a-z]/g, "");

    const linenHtml = `<span class="hk-checklist-item ${t.linen_changed ? 'checked' : ''}">${t.linen_changed ? '✓' : '○'} Linens</span>`;
    const amenHtml = `<span class="hk-checklist-item ${t.amenities_restocked ? 'checked' : ''}">${t.amenities_restocked ? '✓' : '○'} Amenities</span>`;
    const bathHtml = `<span class="hk-checklist-item ${t.bathroom_sanitized ? 'checked' : ''}">${t.bathroom_sanitized ? '✓' : '○'} Sanitized</span>`;

    let notesText = t.notes || "Standard turnover";
    if (t.inspected_by) {
      notesText += ` • <span style="color: #34d399; font-weight: 500;">Audited by ${t.inspected_by}</span>`;
    }

    let actionButtons = `<div class="hk-actions-group">`;
    if (t.status === "Pending") {
      actionButtons += `<button class="btn-hk-action btn-hk-start" onclick="handleStartCleaningTask(${t.id})">Start Clean</button>`;
    } else if (t.status === "In Progress") {
      actionButtons += `<button class="btn-hk-action btn-hk-clean" onclick="handleMarkTaskCleaned(${t.id})">Mark Cleaned</button>`;
    } else if (t.status === "Cleaned") {
      actionButtons += `<button class="btn-hk-action btn-hk-inspect" onclick="handlePassTaskInspection(${t.id})">Pass Inspection</button>`;
    } else if (t.status === "Inspected") {
      actionButtons += `<span style="font-size: 11px; color: #34d399; font-weight: 600;">✓ Ready for Guest</span>`;
    }

    actionButtons += `
        <button class="btn-hk-action btn-hk-dnd" title="Toggle Do Not Disturb flag for Room ${t.room_number || t.room_id}" onclick="handleToggleRoomDND(${t.room_id})">DND</button>
      </div>
    `;

    tr.innerHTML = `
      <td><span style="font-family: monospace; font-size: 11px; color: var(--text-muted);">#${t.id}</span></td>
      <td>
        <strong style="color: var(--text-high-contrast);">Room ${t.room_number || t.room_id}</strong>
        <span style="font-size: 11px; color: var(--text-muted); display: block;">Fl. ${t.floor || 1} • ${t.room_type || 'Deluxe'}</span>
      </td>
      <td><span style="font-size: 12px; font-weight: 500;">${t.task_type}</span></td>
      <td><span class="hk-priority-badge hk-priority-${priorityClass}">${t.priority}</span></td>
      <td>
        <span style="font-size: 12px; font-weight: 600; color: var(--text-high-contrast);">${t.assigned_housekeeper || 'Maria Santos'}</span>
      </td>
      <td>
        <div class="hk-checklist-pills">
          ${linenHtml} ${amenHtml} ${bathHtml}
        </div>
      </td>
      <td>
        <div style="font-size: 11.5px; color: var(--text-muted); line-height: 1.3;">${notesText}</div>
      </td>
      <td>
        <span class="hk-status-pill hk-status-${statusKey}">${t.status}</span>
      </td>
      <td>${actionButtons}</td>
    `;
    tbody.appendChild(tr);
  });
}

/**
 * Starts cleaning task -> transitions status to 'In Progress'
 */
async function handleStartCleaningTask(taskId) {
  try {
    const res = await fetch(`/api/housekeeping/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "In Progress" }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    showToast(`Task #${taskId} is now In Progress. Room updated to Cleaning.`, "info");
    fetchHousekeepingDashboard();
    fetchHousekeepingTasks(currentHkFilter);
    fetchRooms();
    fetchKPIs();
  } catch (err) {
    showToast(`Failed to update task: ${err.message}`, "error");
  }
}

/**
 * Marks cleaning task complete with checklist -> transitions to 'Cleaned'
 */
async function handleMarkTaskCleaned(taskId) {
  try {
    const res = await fetch(`/api/housekeeping/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "Cleaned",
        linen_changed: true,
        amenities_restocked: true,
        bathroom_sanitized: true,
        notes: "Full turnover completed. Linens fresh, bathroom sanitized.",
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    showToast(`Task #${taskId} marked Cleaned (Pending Quality Inspection).`, "success");
    fetchHousekeepingDashboard();
    fetchHousekeepingTasks(currentHkFilter);
    fetchRooms();
    fetchKPIs();
  } catch (err) {
    showToast(`Failed to mark cleaned: ${err.message}`, "error");
  }
}

/**
 * Passes executive inspection -> transitions to 'Inspected' & releases room to Available
 */
async function handlePassTaskInspection(taskId) {
  try {
    const res = await fetch(`/api/housekeeping/tasks/${taskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "Inspected",
        inspected_by: "Head Housekeeper Sarah Vance",
        inspector_notes: "Approved 5-star quality sanitation inspection.",
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    showToast(`Task #${taskId} passed inspection! Room released to Available inventory.`, "success");
    fetchHousekeepingDashboard();
    fetchHousekeepingTasks(currentHkFilter);
    fetchRooms();
    fetchKPIs();
  } catch (err) {
    showToast(`Inspection failed: ${err.message}`, "error");
  }
}

/**
 * Toggles Do Not Disturb (DND) state for a room
 */
async function handleToggleRoomDND(roomId) {
  try {
    const room = allRoomsData.find((r) => r.id === roomId);
    const newDnd = room ? !room.dnd_status : true;

    const res = await fetch(`/api/rooms/${roomId}/housekeeping`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cleanliness_status: room ? room.cleanliness_status : "Clean",
        dnd_status: newDnd,
        notes: newDnd ? "Guest toggled DND active." : "DND flag cleared.",
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    showToast(`Room ${room ? room.room_number : roomId} DND is now ${newDnd ? 'ACTIVE (Do Not Disturb)' : 'OFF'}.`, "info");
    fetchHousekeepingDashboard();
    fetchRooms();
  } catch (err) {
    showToast(`Failed to toggle DND: ${err.message}`, "error");
  }
}

/**
 * Opens dispatch housekeeping task modal and populates rooms
 */
function openDispatchHkTaskModal() {
  const modal = document.getElementById("dispatchHkTaskModal");
  const roomSelect = document.getElementById("hkModalRoomSelect");
  if (!modal || !roomSelect) return;

  roomSelect.innerHTML = '<option value="">Select Room...</option>';
  allRoomsData.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = `Room ${r.room_number} - ${r.room_type} (${r.status}, ${r.cleanliness_status})`;
    roomSelect.appendChild(opt);
  });

  modal.classList.remove("hidden");
}

function closeDispatchHkTaskModal() {
  const modal = document.getElementById("dispatchHkTaskModal");
  if (modal) modal.classList.add("hidden");
}

async function handleDispatchHkTaskSubmit(e) {
  e.preventDefault();
  const roomId = parseInt(document.getElementById("hkModalRoomSelect").value, 10);
  const taskType = document.getElementById("hkModalTaskType").value;
  const priority = document.getElementById("hkModalPriority").value;
  const attendant = document.getElementById("hkModalAttendant").value;
  const notes = document.getElementById("hkModalNotes").value.trim();

  if (!roomId) {
    showToast("Please select a target room.", "error");
    return;
  }

  try {
    const res = await fetch("/api/housekeeping/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room_id: roomId,
        task_type: taskType,
        priority: priority,
        assigned_housekeeper: attendant,
        notes: notes,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    showToast(`Housekeeping task dispatched for Room! Assigned to ${attendant}.`, "success");
    closeDispatchHkTaskModal();
    fetchHousekeepingDashboard();
    fetchHousekeepingTasks(currentHkFilter);
    fetchRooms();
  } catch (err) {
    showToast(`Dispatch failed: ${err.message}`, "error");
  }
}

// ==========================================
// Module 5: Keycard & Access Control Security Controller
// ==========================================

let currentKeycardsData = [];
let currentAccessLogsData = [];
let currentSecSearch = "";
let currentSecStatusFilter = "";
let currentSecTypeFilter = "";
let currentSecOutcomeFilter = "";

/**
 * Fetches executive security dashboard metrics: active cards, master keys, taps, denied intrusions, revoked
 */
async function fetchSecurityDashboard() {
  try {
    const res = await fetch("/api/access-control/dashboard");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const elActive = document.getElementById("secKpiActive");
    const elMaster = document.getElementById("secKpiMaster");
    const elTaps = document.getElementById("secKpiTaps");
    const elDenied = document.getElementById("secKpiDenied");
    const elRevoked = document.getElementById("secKpiRevoked");

    if (elActive) elActive.textContent = data.active_cards;
    if (elMaster) elMaster.textContent = data.master_cards;
    if (elTaps) elTaps.textContent = data.taps_today;
    if (elDenied) elDenied.textContent = data.denied_intrusions_today;
    if (elRevoked) elRevoked.textContent = data.revoked_cards;
  } catch (err) {
    console.error("fetchSecurityDashboard error:", err);
  }
}

/**
 * Fetches keycards directory with optional multi-filtering
 */
async function fetchKeycards() {
  const tbody = document.getElementById("keycardsTableBody");
  const emptyPlaceholder = document.getElementById("keycardsEmpty");
  if (!tbody) return;

  try {
    const params = new URLSearchParams();
    if (currentSecSearch) params.append("search", currentSecSearch);
    if (currentSecStatusFilter) params.append("status", currentSecStatusFilter);
    if (currentSecTypeFilter) params.append("card_type", currentSecTypeFilter);

    const qs = params.toString();
    const url = qs ? `/api/keycards?${qs}` : "/api/keycards";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    currentKeycardsData = await res.json();
    renderKeycardsTable(currentKeycardsData);
  } catch (err) {
    console.error("fetchKeycards error:", err);
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">Failed to load keycards.</td></tr>`;
  }
}

/**
 * Renders keycards into keycardsTableBody
 */
function renderKeycardsTable(cards) {
  const tbody = document.getElementById("keycardsTableBody");
  const emptyPlaceholder = document.getElementById("keycardsEmpty");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!cards || cards.length === 0) {
    if (emptyPlaceholder) emptyPlaceholder.classList.remove("hidden");
    return;
  }
  if (emptyPlaceholder) emptyPlaceholder.classList.add("hidden");

  cards.forEach((k) => {
    const tr = document.createElement("tr");

    // Card type badge
    let typeClass = "badge-type-guest";
    if (k.card_type === "Staff Master") typeClass = "badge-type-master";
    else if (k.card_type === "Housekeeping") typeClass = "badge-type-housekeeping";
    else if (k.card_type === "Maintenance") typeClass = "badge-type-maintenance";
    else if (k.card_type === "Emergency Override") typeClass = "badge-type-emergency";

    // Status badge
    let statusClass = "badge-card-active";
    if (k.status === "Revoked") statusClass = "badge-card-revoked";
    else if (k.status === "Suspended") statusClass = "badge-card-suspended";
    else if (k.status === "Expired") statusClass = "badge-card-revoked";

    // Room info
    let roomDisplay = k.room_id ? `Room ${k.room ? k.room.room_number : k.room_id}` : `<span style="color: #a5b4fc; font-weight: 600;">Universal Master</span>`;

    // Action buttons
    let actionButtons = `
      <div class="table-actions-group">
        <button type="button" class="btn-card-tap" onclick="openDoorTapModalWithCard('${k.card_uid}', ${k.room_id || 'null'})" title="Simulate Door Tap">Tap Lock</button>
    `;
    if (k.status === "Active") {
      actionButtons += `<button type="button" class="btn-card-revoke" onclick="handleRevokeKeycard(${k.id}, '${k.card_uid}')">Revoke</button>`;
    } else {
      actionButtons += `<span style="font-size: 11px; color: var(--text-muted); align-self: center;">Deactivated</span>`;
    }
    actionButtons += `</div>`;

    const holderSub = k.booking_id ? `<span style="font-size: 11px; color: var(--text-muted); display: block;">Booking Folio #${k.booking_id}</span>` : `<span style="font-size: 11px; color: var(--text-muted); display: block;">${k.issued_by || 'Staff Credential'}</span>`;

    tr.innerHTML = `
      <td><span class="card-uid-mono">${escapeHtml(k.card_uid)}</span></td>
      <td>
        <strong style="color: var(--text-high-contrast);">${escapeHtml(k.holder_name)}</strong>
        ${holderSub}
      </td>
      <td><span class="${typeClass}">${escapeHtml(k.card_type)}</span></td>
      <td>${roomDisplay}</td>
      <td><span style="font-size: 12px; color: var(--text-muted);">${formatTimestamp(k.issued_at)}</span></td>
      <td><span class="${statusClass}">${escapeHtml(k.status)}</span></td>
      <td>${actionButtons}</td>
    `;
    tbody.appendChild(tr);
  });
}

/**
 * Fetches door access audit logs with optional outcome filtering
 */
async function fetchAccessLogs() {
  const tbody = document.getElementById("accessLogsTableBody");
  const emptyPlaceholder = document.getElementById("accessLogsEmpty");
  if (!tbody) return;

  try {
    const params = new URLSearchParams();
    if (currentSecOutcomeFilter === "Granted") {
      params.append("access_granted", "true");
    } else if (currentSecOutcomeFilter === "Denied") {
      params.append("access_granted", "false");
    }

    const qs = params.toString();
    const url = qs ? `/api/access-control/logs?${qs}` : "/api/access-control/logs";
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    currentAccessLogsData = await res.json();
    renderAccessLogsTable(currentAccessLogsData);
  } catch (err) {
    console.error("fetchAccessLogs error:", err);
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Failed to load access logs.</td></tr>`;
  }
}

/**
 * Renders door tap access audit events into accessLogsTableBody
 */
function renderAccessLogsTable(logs) {
  const tbody = document.getElementById("accessLogsTableBody");
  const emptyPlaceholder = document.getElementById("accessLogsEmpty");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!logs || logs.length === 0) {
    if (emptyPlaceholder) emptyPlaceholder.classList.remove("hidden");
    return;
  }
  if (emptyPlaceholder) emptyPlaceholder.classList.add("hidden");

  logs.forEach((l) => {
    const tr = document.createElement("tr");

    const badgeClass = l.access_granted ? "badge-granted" : "badge-denied";
    const icon = l.access_granted ? "✓" : "✕";

    const holderInfo = l.keycard ? `${escapeHtml(l.keycard.holder_name)} <span style="font-size: 11px; color: var(--text-muted);">(${escapeHtml(l.keycard.card_type)})</span>` : `<span style="font-size: 11px; color: var(--text-muted);">Unregistered RFID token</span>`;

    tr.innerHTML = `
      <td><span class="table-folio-id">${formatTimestamp(l.attempted_at)}</span></td>
      <td><span class="card-uid-mono">${escapeHtml(l.card_uid)}</span></td>
      <td><strong>Room ${l.room ? l.room.room_number : l.room_id}</strong></td>
      <td><span style="font-size: 12px; color: var(--text-high-contrast);">${escapeHtml(l.reader_location || 'Room Exterior Reader')}</span></td>
      <td>${holderInfo}</td>
      <td><span class="${badgeClass}">${icon} ${escapeHtml(l.event_type)}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

/**
 * Revokes a keycard immediately
 */
async function handleRevokeKeycard(cardId, cardUid) {
  const reason = prompt(`Provide audit reason for revoking keycard ${cardUid}:`, "Reported lost / guest checkout");
  if (!reason || !reason.trim()) return;

  try {
    const res = await fetch(`/api/keycards/${cardId}/revoke`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason.trim() }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    showToast(`Keycard ${cardUid} has been deactivated & revoked.`, "info");
    fetchKeycards();
    fetchSecurityDashboard();
    fetchAuditLogs();
  } catch (err) {
    showToast(`Revocation failed: ${err.message}`, "error");
  }
}

/**
 * Populates and opens Issue Keycard Modal
 */
function openIssueCardModal() {
  const modal = document.getElementById("issueCardModal");
  const form = document.getElementById("issueKeycardForm");
  const roomSelect = document.getElementById("kcModalRoom");
  if (!modal || !roomSelect) return;

  roomSelect.innerHTML = '<option value="">Select Room (Optional for Master)...</option>';
  allRoomsData.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = `Room ${r.room_number} (${r.room_type} - ${r.status})`;
    roomSelect.appendChild(opt);
  });

  if (form) form.reset();
  modal.classList.remove("hidden");
}

function closeIssueCardModal() {
  const modal = document.getElementById("issueCardModal");
  if (modal) modal.classList.add("hidden");
}

/**
 * Handles encoding and issuing a keycard
 */
async function handleIssueKeycardSubmit(e) {
  e.preventDefault();
  const holderName = document.getElementById("kcModalHolder").value.trim();
  const cardType = document.getElementById("kcModalType").value;
  const roomVal = document.getElementById("kcModalRoom").value;
  const customUid = document.getElementById("kcModalUid").value.trim();
  const notes = document.getElementById("kcModalNotes").value.trim();

  if (!holderName) {
    showToast("Please enter cardholder name.", "error");
    return;
  }

  const payload = {
    card_holder_name: holderName,
    card_type: cardType,
    room_id: roomVal ? parseInt(roomVal, 10) : null,
    card_uid: customUid || null,
    issued_by: "Security Front Desk",
    notes: notes || null,
  };

  try {
    const res = await fetch("/api/keycards/issue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const card = await res.json();
    showToast(`Keycard ${card.card_uid} encoded & activated for ${card.holder_name}!`, "success");
    closeIssueCardModal();
    fetchKeycards();
    fetchSecurityDashboard();
    fetchAuditLogs();
  } catch (err) {
    showToast(`Issuance failed: ${err.message}`, "error");
  }
}

/**
 * Opens door reader tap modal with optional pre-selected card & room
 */
function openDoorTapModalWithCard(cardUid = null, roomId = null) {
  const modal = document.getElementById("doorTapModal");
  const roomSelect = document.getElementById("tapModalRoomSelect");
  const cardSelect = document.getElementById("tapModalCardSelect");
  const customUid = document.getElementById("tapModalCustomUid");
  const resultBanner = document.getElementById("tapResultBanner");
  if (!modal || !roomSelect || !cardSelect) return;

  if (resultBanner) resultBanner.classList.add("hidden");

  // Populate rooms
  roomSelect.innerHTML = '<option value="">Choose Room Door...</option>';
  allRoomsData.forEach((r) => {
    const opt = document.createElement("option");
    opt.value = r.id;
    opt.textContent = `Room ${r.room_number} (${r.room_type} - ${r.status})`;
    if (roomId && r.id === roomId) opt.selected = true;
    roomSelect.appendChild(opt);
  });

  // Populate registered cards
  cardSelect.innerHTML = '<option value="">Choose Registered Card...</option>';
  currentKeycardsData.forEach((k) => {
    const opt = document.createElement("option");
    opt.value = k.card_uid;
    const roomStr = k.room_id ? `Room ${k.room ? k.room.room_number : k.room_id}` : "Master";
    opt.textContent = `${k.card_uid} — ${k.holder_name} (${k.card_type}, ${roomStr}, ${k.status})`;
    if (cardUid && k.card_uid === cardUid) opt.selected = true;
    cardSelect.appendChild(opt);
  });

  if (customUid) customUid.value = "";
  modal.classList.remove("hidden");
}

function closeDoorTapModal() {
  const modal = document.getElementById("doorTapModal");
  if (modal) modal.classList.add("hidden");
}

/**
 * Simulates physical door tap against electronic lock reader
 */
async function handleExecuteDoorTap() {
  const roomSelect = document.getElementById("tapModalRoomSelect");
  const cardSelect = document.getElementById("tapModalCardSelect");
  const customUidInput = document.getElementById("tapModalCustomUid");
  const banner = document.getElementById("tapResultBanner");
  const title = document.getElementById("tapResultTitle");
  const msg = document.getElementById("tapResultMessage");
  const icon = document.getElementById("tapResultIcon");
  const time = document.getElementById("tapResultTime");

  const roomId = roomSelect.value ? parseInt(roomSelect.value, 10) : null;
  const cardUid = customUidInput.value.trim() || cardSelect.value;

  if (!roomId) {
    showToast("Please choose target room door lock.", "error");
    return;
  }
  if (!cardUid) {
    showToast("Please select or enter an RFID keycard UID.", "error");
    return;
  }

  try {
    const res = await fetch("/api/access-control/tap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        card_uid: cardUid,
        room_id: roomId,
        reader_location: `Room ${roomSelect.options[roomSelect.selectedIndex].text.split(' ')[1]} Door Scanner`,
      }),
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || `HTTP ${res.status}`);

    if (banner) {
      banner.classList.remove("hidden");
      if (result.access_granted) {
        banner.className = "tap-simulation-display granted";
        if (title) title.textContent = "Access Granted — Door Unlocked";
        if (icon) icon.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
      } else {
        banner.className = "tap-simulation-display denied";
        if (title) title.textContent = "Access Denied — Lock Engaged";
        if (icon) icon.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
      }
      if (msg) msg.textContent = result.message;
      if (time) time.textContent = `${result.event_type} • ${result.timestamp ? result.timestamp.replace('T', ' ').split('.')[0] : 'Just now'}`;
    }

    fetchSecurityDashboard();
    fetchAccessLogs();
  } catch (err) {
    showToast(`Door tap failed: ${err.message}`, "error");
  }
}


