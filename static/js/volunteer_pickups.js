/**
 * Volunteer Pickups & Delivery Management
 * Handles donation acceptance, delivery routing, live tracking, and map display
 * * ARCHITECTURE:
 * - Pickup Map (Mode A): Multi-stop TSP route from volunteer -> restaurants
 * - Delivery Map (Mode B): Simple route from volunteer -> nearest camp
 * Both maps use separate instances to avoid conflicts
 */

// ============ GLOBAL STATE ============
let pickupMapInstance = null;
let pickupRoutingControl = null;
let volunteerPickupMarker = null;
let liveTrackingWatchId = null;
let currentVolunteerPosition = null;

// ============ CUSTOM ICONS ============
const bikeIcon = L.divIcon({
    className: 'volunteer-marker',
    html: `<div style="
        width: 36px; height: 36px; 
        background: #10b981; 
        border-radius: 50%; 
        border: 3px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        display: flex; align-items: center; justify-content: center;
    ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
            <circle cx="5.5" cy="17.5" r="3.5"/>
            <circle cx="18.5" cy="17.5" r="3.5"/>
            <path d="M15 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm-3 11.5V14l-3-3 4-3 2 3h2"/>
        </svg>
    </div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18]
});

const campIcon = L.divIcon({
    className: 'camp-marker',
    html: `<div style="
        width: 36px; height: 36px; 
        background: #ef4444; 
        border-radius: 50%; 
        border: 3px solid white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        display: flex; align-items: center; justify-content: center;
    ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
            <polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
    </div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18]
});

// Create numbered restaurant icon
function createRestaurantIcon(number) {
    return L.divIcon({
        className: 'restaurant-marker',
        html: `<div style="
            width: 32px; height: 32px; 
            background: #3b82f6; 
            border-radius: 50%; 
            border: 2px solid white;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            display: flex; align-items: center; justify-content: center;
            color: white; font-weight: 700; font-size: 14px;
        ">${number}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16]
    });
}

// ============ PAGE INITIALIZATION ============
document.addEventListener('DOMContentLoaded', function () {
    // Start live location tracking
    startLiveLocationTracking();
    
    // Auto-initialize map on page load
    setTimeout(() => {
        initializePickupMode();
    }, 300);
});

/**
 * Initialize Pickup Mode - handles all map logic and state management
 */
function initializePickupMode() {
    const pickupList = document.getElementById('pickup-list');
    if (!pickupList) return;
    
    const pickupCards = pickupList.querySelectorAll('[data-donation-id]');
    console.log('[v0] Total pickup cards found:', pickupCards.length);
    
    if (pickupCards.length === 0) {
        // No pickups at all
        hideAllPickupMode();
        return;
    }
    
    // Filter pickups by status
    const uncollectedPickups = Array.from(pickupCards).filter(card => 
        card.getAttribute('data-status') !== 'collected'
    );
    const collectedPickups = Array.from(pickupCards).filter(card => 
        card.getAttribute('data-status') === 'collected'
    );
    
    console.log('[v0] Uncollected pickups:', uncollectedPickups.length, 'Collected pickups:', collectedPickups.length);
    
    if (uncollectedPickups.length > 0) {
        // Scenario 1: Show map with route to uncollected restaurants
        console.log('[v0] Scenario 1: There are uncollected pickups - showing map');
        showPickupMapMode();
    } else if (collectedPickups.length > 0) {
        // Scenario 2: All collected, show delivery button
        console.log('[v0] Scenario 2: All items collected - showing delivery button');
        hidePickupMapMode();
        showDeliveryButton();
    } else {
        // Scenario 3: No pickups
        hideAllPickupMode();
    }
}

/**
 * Show pickup map mode - display map and calculate route
 */
function showPickupMapMode() {
    const mapContainer = document.getElementById('pickup-map-container');
    const infoBanner = document.getElementById('route-info-banner');
    const deliveryBtn = document.getElementById('delivery-button-container');
    
    if (mapContainer) mapContainer.style.display = 'block';
    if (infoBanner) infoBanner.style.display = 'none'; // Will show after route is calculated
    if (deliveryBtn) deliveryBtn.style.display = 'none';
    
    // Auto-calculate route
    setTimeout(() => {
        calculateOptimizedRoute();
    }, 300);
}

/**
 * Hide pickup map mode - remove map
 */
function hidePickupMapMode() {
    const mapContainer = document.getElementById('pickup-map-container');
    const infoBanner = document.getElementById('route-info-banner');
    
    if (mapContainer) mapContainer.style.display = 'none';
    if (infoBanner) infoBanner.style.display = 'none';
}

/**
 * Show delivery button mode
 */
function showDeliveryButton() {
    const deliveryBtn = document.getElementById('delivery-button-container');
    if (deliveryBtn) {
        deliveryBtn.style.display = 'block';
    }
}

/**
 * Hide all pickup mode elements
 */
function hideAllPickupMode() {
    hidePickupMapMode();
    const deliveryBtn = document.getElementById('delivery-button-container');
    if (deliveryBtn) deliveryBtn.style.display = 'none';
}

// ============ PICKUP MAP (Mode A - Multi-stop TSP) ============

/**
 * Calculate and display optimized pickup route
 * Called when user clicks "Calculate Best Route" button
 */
function calculateOptimizedRoute() {
    const btn = document.getElementById('calculate-route-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner"></span> Calculating...';
    }
    
    // Get current GPS position if available
    const requestBody = {};
    if (currentVolunteerPosition) {
        requestBody.current_lat = currentVolunteerPosition.lat;
        requestBody.current_lon = currentVolunteerPosition.lon;
    }
    
    fetch('/api/calculate-pickup-route/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(requestBody)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayPickupRoute(data);
            showToast('Optimal route calculated!', 'success');
        } else {
            // Silently fail if just no routes (e.g. after cancellation)
        }
    })
    .catch(error => {
        console.error('[v0] Error calculating route:', error);
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                <circle cx="12" cy="10" r="3"/>
            </svg> Recalculate Route`;
        }
    });
}

/**
 * Display the calculated pickup route on the map
 * @param {Object} data - Route data from API
 */
function displayPickupRoute(data) {
    const mapContainer = document.getElementById('pickup-map-container');
    const infoBanner = document.getElementById('route-info-banner');
    const mapElement = document.getElementById('pickup-route-map');
    
    if (!mapContainer || !mapElement) {
        console.error('[v0] Pickup map container not found');
        return;
    }
    
    // Show the map container
    mapContainer.style.display = 'block';
    if (infoBanner) infoBanner.style.display = 'flex';
    
    // Update route info display
    const distanceEl = document.getElementById('route-distance');
    const timeEl = document.getElementById('route-time');
    const stopsEl = document.getElementById('route-stops');
    
    if (distanceEl) distanceEl.textContent = data.total_distance_km;
    if (timeEl) timeEl.textContent = data.estimated_time_minutes;
    if (stopsEl) stopsEl.textContent = data.total_pickups;
    
    // Update pickup order badges in the list
    data.route.forEach((loc, index) => {
        if (index > 0) { // Skip volunteer location (index 0)
            const badge = document.getElementById(`order-badge-${loc.id}`);
            if (badge) {
                badge.textContent = index;
                badge.style.display = 'inline-flex';
            }
            // Highlight the first pickup
            const card = document.getElementById(`pickup-card-${loc.id}`);
            if (card && index === 1) {
                card.classList.add('highlighted');
            }
        }
    });
    
    // Initialize or reinitialize the map
    if (pickupMapInstance) {
        pickupMapInstance.remove();
        pickupMapInstance = null;
    }
    
    pickupMapInstance = L.map('pickup-route-map', {
        zoomControl: true,
        attributionControl: false
    });
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(pickupMapInstance);
    
    // Ensure map renders correctly after container becomes visible
    // CRITICAL: This fixes "map not rendering"
    console.log('[v0] Map initialized, waiting for rendering');
    setTimeout(() => {
        console.log('[v0] Invalidating map size');
        pickupMapInstance.invalidateSize(true);
    }, 150);
    
    // Extra invalidation for stubborn rendering
    setTimeout(() => {
        pickupMapInstance.invalidateSize(true);
    }, 500);
    
    // Create waypoints from route data
    const waypoints = data.route.map(loc => L.latLng(loc.lat, loc.lon));
    
    // --- TEMPORARILY DISABLED ROUTING PATH (User Request) ---
    // Instead, we just add markers and fit bounds manually so map shows
    
    // 1. Add Markers manually
    data.route.forEach((loc, index) => {
        if (index === 0) {
            // Volunteer marker
            volunteerPickupMarker = L.marker([loc.lat, loc.lon], { 
                icon: bikeIcon,
                zIndexOffset: 1000
            }).addTo(pickupMapInstance);
        } else {
            // Restaurant markers
            L.marker([loc.lat, loc.lon], { 
                icon: createRestaurantIcon(index) 
            }).addTo(pickupMapInstance).bindPopup(`<strong>Stop ${index}: ${loc.name}</strong>`);
        }
    });

    // 2. Fit Bounds so map is centered correctly
    if (waypoints.length > 0) {
        const bounds = L.latLngBounds(waypoints);
        pickupMapInstance.fitBounds(bounds, { padding: [50, 50] });
    }
    
    // --- END OF MANUAL MAP SETUP ---
    
    // Show live tracking indicator
    const trackingStatus = document.getElementById('live-tracking-status');
    if (trackingStatus) trackingStatus.style.display = 'flex';
}

// ============ PICKUP MAP SPECIFIC CODE ============
// (Delivery map code is now in volunteer_deliveries.js - separate file)

// ============ LIVE LOCATION TRACKING ============

/**
 * Start GPS-based live location tracking
 */
function startLiveLocationTracking() {
    if (!navigator.geolocation) {
        console.warn('[v0] Geolocation not supported');
        return;
    }
    
    liveTrackingWatchId = navigator.geolocation.watchPosition(
        (position) => {
            const { latitude, longitude, accuracy } = position.coords;
            
            currentVolunteerPosition = { lat: latitude, lon: longitude };
            
            // Update volunteer marker on pickup map
            if (volunteerPickupMarker) {
                volunteerPickupMarker.setLatLng([latitude, longitude]);
            }
            
            // Send location update to server (throttled)
            sendLocationUpdate(latitude, longitude, accuracy);
        },
        (error) => {
            console.warn('[v0] Geolocation error:', error.message);
        },
        {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 10000
        }
    );
}

/**
 * Stop live location tracking
 */
function stopLiveLocationTracking() {
    if (liveTrackingWatchId !== null) {
        navigator.geolocation.clearWatch(liveTrackingWatchId);
        liveTrackingWatchId = null;
    }
}

// Throttle location updates to server
let lastLocationUpdate = 0;
const LOCATION_UPDATE_INTERVAL = 30000; // 30 seconds

/**
 * Send location update to server
 */
function sendLocationUpdate(latitude, longitude, accuracy) {
    const now = Date.now();
    if (now - lastLocationUpdate < LOCATION_UPDATE_INTERVAL) return;
    lastLocationUpdate = now;
    
    const csrftoken = getCookie('csrftoken');
    
    fetch('/api/update-volunteer-location/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({
            latitude: latitude,
            longitude: longitude,
            accuracy: accuracy
        })
    }).catch(err => console.warn('[v0] Failed to send location update:', err));
}

// ============ DONATION ACTIONS ============

/**
 * Accept a donation via AJAX
 * NO RELOAD: DOM updated async, item moved from available to active pickups
 * @param {number} donationId - ID of the donation to accept
 */
function acceptDonation(donationId) {
    const csrftoken = getCookie('csrftoken');
    const acceptBtn = document.getElementById(`accept-btn-${donationId}`);
    
    if (!acceptBtn) {
        console.error('[v0] Accept button not found for donation:', donationId);
        return;
    }
    
    acceptBtn.disabled = true;
    acceptBtn.textContent = 'Accepting...';
    acceptBtn.style.cursor = 'wait';
    
    fetch(`/donation/accept/${donationId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            acceptBtn.textContent = 'Accepted!';
            acceptBtn.classList.remove('action-button');
            acceptBtn.style.backgroundColor = '#10b981';
            acceptBtn.style.color = 'white';
            acceptBtn.style.cursor = 'default';
            
            showToast(data.message || 'Donation accepted! Please pick it up within 30 minutes.', 'success');
            
            // NO RELOAD: Smoothly remove from available list and add to active list
            setTimeout(() => {
                const row = document.getElementById(`donation-row-${donationId}`);
                if (row) {
                    row.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(-20px)';
                    setTimeout(() => {
                        row.remove();
                        console.log('[v0] Donation removed from available list');
                        
                        // NEW: Immediately add to active list if data returned from server
                        if (data.donation) {
                            addPickupCardToActiveList(data.donation);
                            // Refresh map logic to include new point
                            setTimeout(() => {
                                initializePickupMode();
                            }, 500);
                        } else {
                            // Fallback if backend doesn't send data yet (should not happen with updated view)
                            setTimeout(() => {
                                initializePickupMode();
                            }, 300);
                        }
                        
                        // Check if available donations list is empty
                        const availableList = document.getElementById('available-donations-tbody');
                        if (availableList) {
                            const remainingDonations = availableList.querySelectorAll('tr[id^="donation-row-"]');
                            if (remainingDonations.length === 0) {
                                console.log('[v0] No more available donations');
                                const container = document.getElementById('available-donations-container');
                                if (container) {
                                    container.innerHTML = '<p class="empty-state">There are no available donations right now. Check back later.</p>';
                                }
                            }
                        }
                    }, 300);
                }
            }, 500);
        } else {
            acceptBtn.disabled = false;
            acceptBtn.textContent = 'Accept';
            acceptBtn.style.cursor = 'pointer';
            showToast(data.message || 'Failed to accept donation', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error accepting donation:', error);
        acceptBtn.disabled = false;
        acceptBtn.textContent = 'Accept';
        acceptBtn.style.cursor = 'pointer';
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Helper: Add a new pickup card to the active list dynamically
 */
function addPickupCardToActiveList(donation) {
    const list = document.getElementById('pickup-list');
    
    // If list doesn't exist (e.g., page loaded with 0 pickups and rendered the "No Active Pickups" empty state),
    // we must reload because the HTML structure for the map and list isn't there.
    if (!list) {
        console.log('[v0] Pickup list container not found, reloading to render active state...');
        window.location.reload();
        return;
    }

    // Check if already exists to prevent duplicates
    if (document.getElementById(`pickup-card-${donation.pk}`)) return;

    const card = document.createElement('div');
    card.className = 'pickup-item-card';
    card.id = `pickup-card-${donation.pk}`;
    card.setAttribute('data-donation-id', donation.pk);
    card.setAttribute('data-status', 'accepted');
    card.setAttribute('data-lat', donation.latitude);
    card.setAttribute('data-lon', donation.longitude);
    
    card.innerHTML = `
        <div style="display: flex; align-items: center; flex: 1;">
            <span class="pickup-order-badge" id="order-badge-${donation.pk}" style="display: none;">-</span>
            <div class="pickup-item-info" style="flex: 1;">
                <h4>${donation.restaurant_name}</h4>
                <p>${donation.food_description}</p>
                <p class="address-text">${donation.pickup_address}</p>
            </div>
        </div>
        <div class="pickup-item-status" style="display: flex; gap: 8px; align-items: center;">
            <button class="btn-collect" id="collect-btn-${donation.pk}" onclick="markAsCollected(${donation.pk})">
                Mark as Collected
            </button>
            <button class="btn-cancel" id="cancel-btn-${donation.pk}" onclick="cancelPickup(${donation.pk})" title="Cancel this pickup">
                Cancel
            </button>
        </div>
    `;
    
    list.appendChild(card);
    
    // Update active count in stats bar
    const activeCountEl = document.getElementById('active-count');
    if (activeCountEl) {
         const parts = activeCountEl.textContent.split('/');
         let current = parseInt(parts[0]) || 0;
         activeCountEl.textContent = `${current + 1}/10`;
    }
    
    // Ensure map container is visible
    const mapContainer = document.getElementById('pickup-map-container');
    if (mapContainer) mapContainer.style.display = 'block';
}

/**
 * Mark a donation as collected via AJAX
 * FIXED: Keeps item in list, shows "Collected" badge, checks if ALL collected, shows delivery button
 * @param {number} donationId - ID of the donation to mark as collected
 */
function markAsCollected(donationId) {
    const csrftoken = getCookie('csrftoken');
    const collectBtn = document.getElementById(`collect-btn-${donationId}`);
    const pickupCard = document.getElementById(`pickup-card-${donationId}`);

    if (!collectBtn) return;

    collectBtn.disabled = true;
    collectBtn.textContent = 'Updating...';

    fetch(`/donation/collected/${donationId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message || 'Marked as collected!', 'success');
            
            // PERSISTENT: Keep item in list, replace button with "Collected" badge
            const statusDiv = collectBtn.parentElement;
            collectBtn.style.display = 'none'; // Hide the button
            
            // Create and show collected badge
            const badge = document.createElement('span');
            badge.className = 'status-badge status-collected';
            badge.textContent = 'Collected';
            statusDiv.insertBefore(badge, collectBtn);
            
            // Update the card's data-status attribute
            if (pickupCard) {
                pickupCard.setAttribute('data-status', 'collected');
            }
            
            // Update collected count
            const collectedCountEl = document.getElementById('collected-count');
            if (collectedCountEl) {
                const currentCount = parseInt(collectedCountEl.textContent) || 0;
                collectedCountEl.textContent = currentCount + 1;
            }
            
            // Re-evaluate map visibility logic after marking as collected
            setTimeout(() => {
                initializePickupMode();
            }, 300);
        } else {
            collectBtn.disabled = false;
            collectBtn.textContent = 'Mark as Collected';
            showToast(data.message || 'Failed to update status', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error marking as collected:', error);
        collectBtn.disabled = false;
        collectBtn.textContent = 'Mark as Collected';
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Cancel a pickup (reset donation to PENDING)
 * FIXED: Immediately removes item from DOM, refreshes map, AND adds it back to Available list
 * @param {number} donationId - ID of the donation to cancel
 */
function cancelPickup(donationId) {
    console.log('[v0] cancelPickup called for donation ID:', donationId);
    
    if (!confirm('Are you sure you want to cancel this pickup? The donation will become available for other volunteers.')) {
        return;
    }
    
    const csrftoken = getCookie('csrftoken');
    const pickupCard = document.getElementById(`pickup-card-${donationId}`);
    const cancelBtn = document.getElementById(`cancel-btn-${donationId}`);
    
    if (cancelBtn) {
        cancelBtn.disabled = true;
        cancelBtn.textContent = 'Cancelling...';
    }
    
    const url = `/donation/cancel-pickup/${donationId}/`;
    
    fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message || 'Pickup cancelled successfully', 'success');
            
            // 1. Remove the active card from DOM
            if (pickupCard) {
                pickupCard.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                pickupCard.style.opacity = '0';
                pickupCard.style.transform = 'translateX(-20px)';
                setTimeout(() => {
                    pickupCard.remove();
                    
                    // Update collected count if needed (if it was previously collected)
                    const wasCollected = pickupCard.getAttribute('data-status') === 'collected';
                    if (wasCollected) {
                        const collectedCountEl = document.getElementById('collected-count');
                        if (collectedCountEl) {
                            const currentCount = parseInt(collectedCountEl.textContent) || 0;
                            collectedCountEl.textContent = Math.max(0, currentCount - 1);
                        }
                    }

                    // Update Active Count
                    const activeCountEl = document.getElementById('active-count');
                    let currentActiveCount = 0;
                    if (activeCountEl) {
                         // Parse "X/10"
                         const parts = activeCountEl.textContent.split('/');
                         currentActiveCount = parseInt(parts[0]) || 0;
                         currentActiveCount = Math.max(0, currentActiveCount - 1);
                         activeCountEl.textContent = `${currentActiveCount}/10`;
                    }

                    // 2. Add donation back to the "Available" table using data returned from server
                    if (data.donation) {
                        addDonationToAvailableList(data.donation);
                    }

                    // 3. Check for "Limit Reached" buttons and re-enable them if count < 10
                    if (currentActiveCount < 10) {
                        enableLimitReachedButtons();
                    }
                    
                    // Re-evaluate map visibility logic
                    setTimeout(() => {
                        initializePickupMode();
                    }, 300);
                }, 300);
            }
        } else {
            if (cancelBtn) {
                cancelBtn.disabled = false;
                cancelBtn.textContent = 'Cancel';
            }
            showToast(data.message || 'Failed to cancel pickup', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error cancelling pickup:', error);
        if (cancelBtn) {
            cancelBtn.disabled = false;
            cancelBtn.textContent = 'Cancel';
        }
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Adds a cancelled donation back to the Available Donations list
 */
function addDonationToAvailableList(donation) {
    const container = document.getElementById('available-donations-container');
    let tbody = document.getElementById('available-donations-tbody');
    
    // If table doesn't exist (empty state), create it
    if (!tbody && container) {
        container.innerHTML = `
        <table class="data-table">
            <thead>
                <tr><th>Restaurant</th><th>Food Description</th><th>Address</th><th>Action</th></tr>
            </thead>
            <tbody id="available-donations-tbody"></tbody>
        </table>`;
        tbody = document.getElementById('available-donations-tbody');
    }
    
    if (tbody) {
        const tr = document.createElement('tr');
        tr.id = `donation-row-${donation.pk}`;
        tr.style.opacity = '0'; // For animation
        tr.innerHTML = `
            <td data-label="Restaurant"><strong>${donation.restaurant_name}</strong></td>
            <td data-label="Food Description">${donation.food_description}</td>
            <td data-label="Address">${donation.pickup_address}</td>
            <td data-label="Action">
                <button type="button" class="action-button" id="accept-btn-${donation.pk}"
                        data-testid="accept-donation-btn-${donation.pk}" onclick="acceptDonation(${donation.pk})">
                    Accept
                </button>
            </td>
        `;
        tbody.prepend(tr);
        
        // Animate in
        setTimeout(() => {
            tr.style.transition = 'opacity 0.5s ease-in';
            tr.style.opacity = '1';
        }, 50);
    }
}

/**
 * Enables "Limit Reached" buttons when active count drops below limit
 */
function enableLimitReachedButtons() {
    const disabledButtons = document.querySelectorAll('button[data-testid="pickup-limit-reached-btn"]');
    disabledButtons.forEach(btn => {
        // Find the donation ID from the row ID (donation-row-123)
        const row = btn.closest('tr');
        if (row && row.id) {
            const donationId = row.id.replace('donation-row-', '');
            
            // Replace the disabled button with an Accept button
            const newBtn = document.createElement('button');
            newBtn.type = 'button';
            newBtn.className = 'action-button';
            newBtn.id = `accept-btn-${donationId}`;
            newBtn.setAttribute('data-testid', `accept-donation-btn-${donationId}`);
            newBtn.onclick = function() { acceptDonation(donationId); };
            newBtn.textContent = 'Accept';
            
            btn.parentNode.replaceChild(newBtn, btn);
        }
    });
}

// ============ NGO REGISTRATION ACTIONS ============

/**
 * Register with an NGO via AJAX
 * NO RELOAD: DOM updated async, item moved from available to registered
 * @param {number} ngoId - ID of the NGO to register with
 */
function registerWithNGO(ngoId) {
    const csrftoken = getCookie('csrftoken');
    const registerBtn = document.getElementById(`register-btn-${ngoId}`);
    
    if (!registerBtn) return;
    
    registerBtn.disabled = true;
    registerBtn.textContent = 'Registering...';
    
    fetch(`/volunteer/register/ngo/${ngoId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            
            // NO RELOAD: Remove from available, add to registered
            setTimeout(() => {
                const availableRow = document.getElementById(`available-ngo-${ngoId}`);
                if (availableRow) {
                    availableRow.style.transition = 'opacity 0.3s ease-out';
                    availableRow.style.opacity = '0';
                    setTimeout(() => {
                        availableRow.remove();
                        
                        // Check if available list is empty
                        const availableList = document.getElementById('available-ngos-tbody');
                        if (availableList && availableList.querySelectorAll('tr:not(:has(.empty-state))').length === 0) {
                            availableList.innerHTML = '<tr><td colspan="3"><div class="empty-state"><p>No New NGOs Available</p></div></td></tr>';
                        }
                    }, 300);
                }
                
                // Remove empty row if exists in registered list
                const registeredEmpty = document.getElementById('registered-empty');
                if (registeredEmpty) {
                    registeredEmpty.remove();
                }
                
                // Add to registered list (requires data from API response)
                if (data.ngo_name) {
                    const registeredList = document.getElementById('registered-ngos-tbody');
                    if (registeredList) {
                        const newRow = document.createElement('tr');
                        newRow.id = `registered-ngo-${ngoId}`;
                        const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
                        newRow.innerHTML = `
                            <td data-label="NGO Name"><strong>${data.ngo_name}</strong></td>
                            <td data-label="Date Joined">${today}</td>
                            <td data-label="Action">
                                <button type="button" class="action-button-danger" onclick="unregisterFromNGO(${ngoId})">Leave</button>
                            </td>
                        `;
                        registeredList.appendChild(newRow);
                        console.log('[v0] NGO added to registered list');
                    }
                }
            }, 300);
        } else {
            registerBtn.disabled = false;
            registerBtn.textContent = 'Register';
            showToast(data.message || 'Failed to register', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error registering with NGO:', error);
        registerBtn.disabled = false;
        registerBtn.textContent = 'Register';
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Unregister from an NGO via AJAX
 * NO RELOAD: DOM updated async, item moved from registered to available
 * @param {number} ngoId - ID of the NGO to unregister from
 */
function unregisterFromNGO(ngoId) {
    if (!confirm('Are you sure you want to unregister from this NGO?')) {
        return;
    }
    
    const csrftoken = getCookie('csrftoken');
    const unregisterBtn = document.querySelector(`button[onclick="unregisterFromNGO(${ngoId})"]`);
    
    if (unregisterBtn) {
        unregisterBtn.disabled = true;
        unregisterBtn.textContent = 'Leaving...';
    }
    
    fetch(`/volunteer/unregister/ngo/${ngoId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            
            // NO RELOAD: Remove from registered list
            setTimeout(() => {
                const registeredRow = document.getElementById(`registered-ngo-${ngoId}`);
                if (registeredRow) {
                    registeredRow.style.transition = 'opacity 0.3s ease-out';
                    registeredRow.style.opacity = '0';
                    setTimeout(() => {
                        registeredRow.remove();
                        
                        // Check if registered list is empty
                        const registeredList = document.getElementById('registered-ngos-tbody');
                        if (registeredList && registeredList.querySelectorAll('tr:not(:has(.empty-state))').length === 0) {
                            const emptyRow = document.createElement('tr');
                            emptyRow.id = 'registered-empty';
                            emptyRow.innerHTML = '<td colspan="3"><div class="empty-state"><p>Not Registered with Any NGOs</p></div></td>';
                            registeredList.appendChild(emptyRow);
                        }
                    }, 300);
                }
                
                // Add back to available list if data has ngo info
                if (data.ngo_name) {
                    const availableList = document.getElementById('available-ngos-tbody');
                    if (availableList) {
                        // Remove empty state if exists
                        const emptyRow = availableList.querySelector('tr:has(.empty-state)');
                        if (emptyRow) {
                            emptyRow.remove();
                        }
                        
                        const newRow = document.createElement('tr');
                        newRow.id = `available-ngo-${ngoId}`;
                        newRow.innerHTML = `
                            <td data-label="NGO Name"><strong>${data.ngo_name}</strong></td>
                            <td data-label="Address">${data.address || ''}</td>
                            <td data-label="Action">
                                <button type="button" class="action-button" onclick="registerWithNGO(${ngoId})">Join</button>
                            </td>
                        `;
                        availableList.appendChild(newRow);
                        console.log('[v0] NGO returned to available list');
                    }
                }
            }, 300);
        } else {
            if (unregisterBtn) {
                unregisterBtn.disabled = false;
                unregisterBtn.textContent = 'Leave';
            }
            showToast(data.message || 'Failed to unregister', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error unregistering from NGO:', error);
        if (unregisterBtn) {
            unregisterBtn.disabled = false;
            unregisterBtn.textContent = 'Leave';
        }
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Proceed to delivery - finds nearest camp and delivers all collected items
 */
function proceedToDelivery() {
    console.log('[v0] Proceeding to delivery');
    
    // Fetch available camps and find the nearest one
    fetch('/api/nearest-camp/', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.camp_id) {
            // Found a camp, proceed with delivery
            deliverToNearestCamp(data.camp_id);
        } else {
            showToast(data.message || 'No active camps found. Please register with an NGO first.', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error getting nearest camp:', error);
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Deliver to a specific camp via AJAX
 */
function deliverToNearestCamp(campId) {
    const csrftoken = getCookie('csrftoken');
    const deliverBtn = document.getElementById('deliver-btn');
    
    if (deliverBtn) {
        deliverBtn.disabled = true;
        deliverBtn.innerHTML = '<span style="display: inline-flex; align-items: center; gap: 8px;"><span style="display: inline-block; width: 12px; height: 12px; border: 2px solid white; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite;"></span> Delivering...</span>';
    }
    
    fetch(`/donation/deliver/to/${campId}/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message || 'Delivered successfully!', 'success');
            
            // Redirect to deliveries page after a short delay
            setTimeout(() => {
                window.location.href = "/dashboard/volunteer/deliveries/";
            }, 1500);
        } else {
            if (deliverBtn) {
                deliverBtn.disabled = false;
                deliverBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M5 12h14"/>
                    <path d="m12 5 7 7-7 7"/>
                </svg> Deliver to Camp`;
            }
            showToast(data.message || 'Failed to deliver', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error delivering to camp:', error);
        if (deliverBtn) {
            deliverBtn.disabled = false;
            deliverBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14"/>
                <path d="m12 5 7 7-7 7"/>
            </svg> Deliver to Camp`;
        }
        showToast('An error occurred. Please try again.', 'error');
    });
}

// ============ CLEANUP ============
window.addEventListener('beforeunload', function() {
    stopLiveLocationTracking();
});