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
let bikeIcon = null;
let campIcon = null;

// Initialize icons safely (only if L is available to prevent crashes)
if (typeof L !== 'undefined') {
    bikeIcon = L.divIcon({
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

    campIcon = L.divIcon({
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
}

// Create numbered restaurant icon safely
function createRestaurantIcon(number) {
    if (typeof L === 'undefined') return null;
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
    // CRITICAL CHECK: Verify Leaflet is loaded
    if (typeof L === 'undefined') {
        console.error('[v0] Leaflet Library is missing! Map will not load.');
        const mapContainer = document.getElementById('pickup-map-container');
        if (mapContainer) {
            mapContainer.innerHTML = '<div style="padding:20px; text-align:center; color:#ef4444; font-weight:bold;">Error: Map resources not loaded. Please refresh the page.</div>';
        }
        // We do NOT return here, so that button handlers (Cancel/Collect) still work!
    } else {
        // Only start map logic if library exists
        setTimeout(() => {
            initializePickupMode();
        }, 300);
    }
    
    // Always start GPS tracking (it's independent of map library)
    startLiveLocationTracking();
    
    // Initialize Search
    initializeSearch();
});

function initializeSearch() {
    const searchForm = document.querySelector('form[action$="volunteer_manage_pickups"]');
    if (searchForm) {
        // Debounce timer
        let debounceTimer;
        const searchInput = searchForm.querySelector('input[name="q"]');
        
        if (searchInput) {
            searchInput.addEventListener('input', function() {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    performSearch(this.value);
                }, 500);
            });
        }
        
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            performSearch(searchInput ? searchInput.value : '');
        });
    }
}

function performSearch(query) {
    const tbody = document.getElementById('available-donations-tbody');
    if (!tbody) return;
    
    tbody.style.opacity = '0.5';
    
    fetch(`/dashboard/volunteer/pickups/?q=${encodeURIComponent(query)}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            renderAvailableDonations(data.donations);
        }
        tbody.style.opacity = '1';
    })
    .catch(err => {
        console.error('Search error:', err);
        tbody.style.opacity = '1';
    });
}

function renderAvailableDonations(donations) {
    const container = document.getElementById('available-donations-container') || document.querySelector('.content-card:last-child'); // Fallback
    let tbody = document.getElementById('available-donations-tbody');
    
    if (donations.length === 0) {
        if (tbody) {
            tbody.innerHTML = '';
            // Ideally show empty message
             if (!document.getElementById('search-empty-msg')) {
                 const msg = document.createElement('tr');
                 msg.id = 'search-empty-msg';
                 msg.innerHTML = '<td colspan="4" class="empty-state">No donations found matching your search.</td>';
                 tbody.appendChild(msg);
             }
        }
        return;
    }
    
    // Remove empty message if exists
    const emptyMsg = document.getElementById('search-empty-msg');
    if (emptyMsg) emptyMsg.remove();
    
    if (!tbody) return;
    
    tbody.innerHTML = donations.map(d => `
        <tr id="donation-row-${d.pk}">
            <td data-label="Restaurant"><strong>${d.restaurant_name}</strong></td>
            <td data-label="Food Description">${d.food_description}</td>
            <td data-label="Address">${d.pickup_address}</td>
            <td data-label="Action">
                <button type="button" class="action-button" id="accept-btn-${d.pk}" 
                        data-testid="accept-donation-btn-${d.pk}" onclick="acceptDonation(${d.pk})">
                    Accept
                </button>
            </td>
        </tr>
    `).join('');
}

/**
 * Initialize Pickup Mode - handles all map logic and state management
 */
function initializePickupMode() {
    const pickupList = document.getElementById('pickup-list');
    if (!pickupList) return;
    
    const pickupCards = pickupList.querySelectorAll('[data-donation-id]');
    
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
    
    if (uncollectedPickups.length > 0) {
        // Scenario 1: Show map with route to uncollected restaurants
        showPickupMapMode();
    } else if (collectedPickups.length > 0) {
        // Scenario 2: All collected, show delivery button
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
    
    // Hide Delivery elements if visible (SPA switch)
    const deliveryMap = document.getElementById('delivery-mode-container');
    if (deliveryMap) deliveryMap.style.display = 'none';

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
/**
 * Show delivery button mode
 */
function showDeliveryButton() {
    const deliveryBtn = document.getElementById('delivery-button-container');
    if (deliveryBtn) {
        deliveryBtn.style.display = 'block';
        // Removed SPA interceptor - allow link to navigate to delivery page
    }
}


// ============ PICKUP MAP (Mode A - Multi-stop TSP) ============

/**
 * Calculate and display optimized pickup route
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
        } else {
            console.warn('[v0] Route calculation failed, falling back to basic map:', data.message);
            // Fallback: If route calc fails (e.g. no location), still render points
            renderFallbackMap();
        }
    })
    .catch(error => {
        console.error('[v0] Error calculating route:', error);
        // Fallback on error
        renderFallbackMap();
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
    if (typeof L === 'undefined') return;

    const mapContainer = document.getElementById('pickup-map-container');
    const infoBanner = document.getElementById('route-info-banner');
    
    if (!mapContainer) return;
    
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
    setTimeout(() => {
        pickupMapInstance.invalidateSize(true);
    }, 150);
    
    // 1. Add Custom Markers
    data.route.forEach((loc, index) => {
        if (index === 0) {
            // Volunteer marker
            if (bikeIcon) {
                volunteerPickupMarker = L.marker([loc.lat, loc.lon], { 
                    icon: bikeIcon,
                    zIndexOffset: 1000
                }).addTo(pickupMapInstance);
            }
        } else {
            // Restaurant markers
            L.marker([loc.lat, loc.lon], { 
                icon: createRestaurantIcon(index) 
            }).addTo(pickupMapInstance).bindPopup(`<strong>Stop ${index}: ${loc.name}</strong>`);
            
            // Update the badge number in the list
            const badge = document.getElementById(`order-badge-${loc.id}`);
            if (badge) {
                badge.textContent = index;
                badge.style.display = 'inline-flex';
            }
        }
    });

    // 2. Add Routing Path
    if (typeof L.Routing !== 'undefined') {
        const waypoints = data.route.map(loc => L.latLng(loc.lat, loc.lon));
        
        pickupRoutingControl = L.Routing.control({
            waypoints: waypoints,
            router: L.Routing.osrmv1({
                serviceUrl: 'https://router.project-osrm.org/route/v1'
            }),
            lineOptions: {
                styles: [{color: '#3b82f6', opacity: 0.8, weight: 6}]
            },
            createMarker: function() { return null; },
            addWaypoints: false,
            draggableWaypoints: false,
            fitSelectedRoutes: true,
            show: false
        }).addTo(pickupMapInstance);
    } else {
        const bounds = L.latLngBounds(data.route.map(loc => L.latLng(loc.lat, loc.lon)));
        pickupMapInstance.fitBounds(bounds, { padding: [50, 50] });
    }
}

/**
 * FALLBACK: Render map with markers only (when route calc fails)
 * This fixes the "Blank Map" issue on devices without GPS/Location permissions.
 */
function renderFallbackMap() {
    if (typeof L === 'undefined') return;

    const mapContainer = document.getElementById('pickup-map-container');
    if (!mapContainer) return;

    console.log('[v0] Rendering fallback map (markers only)');
    mapContainer.style.display = 'block';

    if (pickupMapInstance) {
        pickupMapInstance.remove();
        pickupMapInstance = null;
    }

    pickupMapInstance = L.map('pickup-route-map', {
        zoomControl: true,
        attributionControl: false
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(pickupMapInstance);

    setTimeout(() => {
        pickupMapInstance.invalidateSize(true);
    }, 150);

    const bounds = L.latLngBounds();
    let hasPoints = false;

    // Add current location if available
    if (currentVolunteerPosition && bikeIcon) {
        volunteerPickupMarker = L.marker([currentVolunteerPosition.lat, currentVolunteerPosition.lon], {
            icon: bikeIcon
        }).addTo(pickupMapInstance);
        bounds.extend([currentVolunteerPosition.lat, currentVolunteerPosition.lon]);
        hasPoints = true;
    }

    // Collect all uncollected pickup points from DOM
    const pickupCards = document.querySelectorAll('.pickup-item-card:not([data-status="collected"])');
    
    pickupCards.forEach((card, index) => {
        const lat = parseFloat(card.getAttribute('data-lat'));
        const lon = parseFloat(card.getAttribute('data-lon'));
        const title = card.querySelector('h4') ? card.querySelector('h4').textContent : 'Pickup';

        if (!isNaN(lat) && !isNaN(lon)) {
            L.marker([lat, lon], {
                icon: createRestaurantIcon(index + 1)
            }).addTo(pickupMapInstance).bindPopup(`<strong>${title}</strong>`);
            
            bounds.extend([lat, lon]);
            hasPoints = true;
        }
    });

    if (hasPoints) {
        pickupMapInstance.fitBounds(bounds, { padding: [50, 50] });
    } else {
        // Default view (e.g. India center) if no points found
        pickupMapInstance.setView([20.5937, 78.9629], 5); 
    }
}

// ============ LIVE LOCATION TRACKING ============

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

function stopLiveLocationTracking() {
    if (liveTrackingWatchId !== null) {
        navigator.geolocation.clearWatch(liveTrackingWatchId);
        liveTrackingWatchId = null;
    }
}

let lastLocationUpdate = 0;
const LOCATION_UPDATE_INTERVAL = 30000; // 30 seconds

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
 */
function acceptDonation(donationId) {
    const csrftoken = getCookie('csrftoken');
    const acceptBtn = document.getElementById(`accept-btn-${donationId}`);
    
    if (!acceptBtn) return;
    
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
            
            showToast(data.message || 'Donation accepted!', 'success');
            
            setTimeout(() => {
                const row = document.getElementById(`donation-row-${donationId}`);
                if (row) {
                    row.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(-20px)';
                    setTimeout(() => {
                        row.remove();
                        
                        if (data.donation) {
                            addPickupCardToActiveList(data.donation);
                            setTimeout(() => { initializePickupMode(); }, 500);
                        } else {
                            setTimeout(() => { initializePickupMode(); }, 300);
                        }
                        
                        // Check empty state
                        const availableList = document.getElementById('available-donations-tbody');
                        if (availableList) {
                            const remainingDonations = availableList.querySelectorAll('tr[id^="donation-row-"]');
                            if (remainingDonations.length === 0) {
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

function addPickupCardToActiveList(donation) {
    const list = document.getElementById('pickup-list');
    if (!list) {
        window.location.reload();
        return;
    }

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
    
    const activeCountEl = document.getElementById('active-count');
    if (activeCountEl) {
         const parts = activeCountEl.textContent.split('/');
         let current = parseInt(parts[0]) || 0;
         activeCountEl.textContent = `${current + 1}/10`;
    }
    
    const mapContainer = document.getElementById('pickup-map-container');
    if (mapContainer) mapContainer.style.display = 'block';
}

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
            
            const statusDiv = collectBtn.parentElement;
            collectBtn.style.display = 'none'; 
            
            const badge = document.createElement('span');
            badge.className = 'status-badge status-collected';
            badge.textContent = 'Collected';
            statusDiv.insertBefore(badge, collectBtn);
            
            if (pickupCard) {
                pickupCard.setAttribute('data-status', 'collected');
            }
            
            const collectedCountEl = document.getElementById('collected-count');
            if (collectedCountEl) {
                const currentCount = parseInt(collectedCountEl.textContent) || 0;
                collectedCountEl.textContent = currentCount + 1;
            }
            
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
            
            if (pickupCard) {
                pickupCard.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                pickupCard.style.opacity = '0';
                pickupCard.style.transform = 'translateX(-20px)';
                setTimeout(() => {
                    pickupCard.remove();
                    
                    // Update collected count if needed
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
                         const parts = activeCountEl.textContent.split('/');
                         currentActiveCount = parseInt(parts[0]) || 0;
                         currentActiveCount = Math.max(0, currentActiveCount - 1);
                         activeCountEl.textContent = `${currentActiveCount}/10`;
                    }

                    if (data.donation) {
                        addDonationToAvailableList(data.donation);
                    }

                    if (currentActiveCount < 10) {
                        enableLimitReachedButtons();
                    }
                    
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

function addDonationToAvailableList(donation) {
    const container = document.getElementById('available-donations-container');
    let tbody = document.getElementById('available-donations-tbody');
    
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
        tr.style.opacity = '0';
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
        setTimeout(() => {
            tr.style.transition = 'opacity 0.5s ease-in';
            tr.style.opacity = '1';
        }, 50);
    }
}

function enableLimitReachedButtons() {
    const disabledButtons = document.querySelectorAll('button[data-testid="pickup-limit-reached-btn"]');
    disabledButtons.forEach(btn => {
        const row = btn.closest('tr');
        if (row && row.id) {
            const donationId = row.id.replace('donation-row-', '');
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
            setTimeout(() => {
                const availableRow = document.getElementById(`available-ngo-${ngoId}`);
                if (availableRow) {
                    availableRow.remove();
                }
                
                const registeredEmpty = document.getElementById('registered-empty');
                if (registeredEmpty) registeredEmpty.remove();
                
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

function unregisterFromNGO(ngoId) {
    if (!confirm('Are you sure you want to unregister from this NGO?')) return;
    
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
            setTimeout(() => {
                const registeredRow = document.getElementById(`registered-ngo-${ngoId}`);
                if (registeredRow) registeredRow.remove();
                
                if (data.ngo_name) {
                    const availableList = document.getElementById('available-ngos-tbody');
                    if (availableList) {
                        const emptyRow = availableList.querySelector('tr:has(.empty-state)');
                        if (emptyRow) emptyRow.remove();
                        
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