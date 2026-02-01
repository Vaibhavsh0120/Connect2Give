/**
 * Volunteer Pickups & Delivery Management
 * Handles donation acceptance, delivery routing, live tracking, and map display
 * 
 * ARCHITECTURE:
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
    
    // Auto-calculate and display route if there are active pickups
    const pickupList = document.getElementById('pickup-list');
    const pickupCards = pickupList ? pickupList.querySelectorAll('[data-donation-id]') : [];
    
    if (pickupCards.length > 0) {
        console.log('[v0] Active pickups found:', pickupCards.length);
        // Auto-trigger route calculation after a short delay to ensure DOM is ready
        setTimeout(() => {
            calculateOptimizedRoute();
        }, 500);
    }
});

// ============ PICKUP MAP (Mode A - Multi-stop TSP) ============

/**
 * Calculate and display optimized pickup route
 * Called when user clicks "Calculate Best Route" button
 */
function calculateOptimizedRoute() {
    const btn = document.getElementById('calculate-route-btn');
    if (!btn) return;
    
    btn.disabled = true;
    btn.innerHTML = '<span class="loading-spinner"></span> Calculating...';
    
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
            showToast(data.message || 'Failed to calculate route', 'error');
        }
    })
    .catch(error => {
        console.error('[v0] Error calculating route:', error);
        showToast('An error occurred. Please try again.', 'error');
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
            <circle cx="12" cy="10" r="3"/>
        </svg> Recalculate Route`;
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
    setTimeout(() => {
        pickupMapInstance.invalidateSize();
    }, 100);
    
    // Create waypoints from route data
    const waypoints = data.route.map(loc => L.latLng(loc.lat, loc.lon));
    
    // Check if Leaflet Routing Machine is available
    if (typeof L.Routing !== 'undefined') {
        // Clear existing routing control
        if (pickupRoutingControl) {
            pickupMapInstance.removeControl(pickupRoutingControl);
        }
        
        // Add routing with road path
        pickupRoutingControl = L.Routing.control({
            waypoints: waypoints,
            routeWhileDragging: false,
            show: false, // Hide turn-by-turn instructions
            addWaypoints: false,
            fitSelectedRoutes: true,
            createMarker: function(i, waypoint) {
                const loc = data.route[i];
                if (i === 0) {
                    // Volunteer marker
                    volunteerPickupMarker = L.marker(waypoint.latLng, { 
                        icon: bikeIcon, 
                        zIndexOffset: 1000 
                    }).bindPopup('<strong>Your Location</strong>');
                    return volunteerPickupMarker;
                } else {
                    // Restaurant markers with order numbers
                    return L.marker(waypoint.latLng, { 
                        icon: createRestaurantIcon(i) 
                    }).bindPopup(`<strong>Stop ${i}: ${loc.name}</strong>`);
                }
            },
            lineOptions: {
                styles: [{ color: '#10b981', weight: 5, opacity: 0.8 }]
            }
        }).addTo(pickupMapInstance);
        
        // Handle route found event
        pickupRoutingControl.on('routesfound', function(e) {
            // Update distance/time with actual road values if available
            if (e.routes && e.routes[0]) {
                const summary = e.routes[0].summary;
                const actualDistance = (summary.totalDistance / 1000).toFixed(2);
                const actualTime = Math.round(summary.totalTime / 60);
                
                if (distanceEl) distanceEl.textContent = actualDistance;
                if (timeEl) timeEl.textContent = actualTime;
            }
        });
    } else {
        // Fallback: Add markers without routing
        data.route.forEach((loc, index) => {
            if (index === 0) {
                volunteerPickupMarker = L.marker([loc.lat, loc.lon], { 
                    icon: bikeIcon, 
                    zIndexOffset: 1000 
                }).addTo(pickupMapInstance).bindPopup('<strong>Your Location</strong>');
            } else {
                L.marker([loc.lat, loc.lon], { 
                    icon: createRestaurantIcon(index) 
                }).addTo(pickupMapInstance).bindPopup(`<strong>Stop ${index}: ${loc.name}</strong>`);
            }
        });
        
        // Draw simple polyline connecting all points
        const latlngs = data.route.map(loc => [loc.lat, loc.lon]);
        L.polyline(latlngs, { color: '#10b981', weight: 4, opacity: 0.8 }).addTo(pickupMapInstance);
        
        // Fit bounds
        pickupMapInstance.fitBounds(latlngs, { padding: [30, 30] });
    }
    
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
            
            // NO RELOAD: Smoothly remove from available list
            setTimeout(() => {
                const row = document.getElementById(`donation-row-${donationId}`);
                if (row) {
                    row.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                    row.style.opacity = '0';
                    row.style.transform = 'translateX(-20px)';
                    setTimeout(() => {
                        row.remove();
                        console.log('[v0] Donation removed from available list');
                        
                        // Check if available donations list is empty
                        const availableList = document.getElementById('available-list');
                        if (availableList) {
                            const remainingDonations = availableList.querySelectorAll('[data-donation-id]');
                            if (remainingDonations.length === 0) {
                                console.log('[v0] No more available donations');
                                availableList.innerHTML = '<div style="text-align: center; padding: 2rem; color: #9ca3af;">No donations available at this time.</div>';
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
 * Mark a donation as collected via AJAX
 * FIXED: Updates DOM immediately, checks if all collected, shows delivery button
 * @param {number} donationId - ID of the donation to mark as collected
 */
function markAsCollected(donationId) {
    const csrftoken = getCookie('csrftoken');
    const collectBtn = document.getElementById(`collect-btn-${donationId}`);
    const pickupCard = document.getElementById(`pickup-card-${donationId}`);
    const cancelBtn = document.getElementById(`cancel-btn-${donationId}`);

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
            
            // FIXED: Update button to show "Collected" status
            collectBtn.textContent = 'Collected ✓';
            collectBtn.style.backgroundColor = '#10b981';
            collectBtn.style.cursor = 'default';
            collectBtn.disabled = true;
            
            // Disable cancel button for collected items
            if (cancelBtn) {
                cancelBtn.disabled = true;
                cancelBtn.style.opacity = '0.5';
            }
            
            // Update collected count
            const collectedCountEl = document.getElementById('collected-count');
            if (collectedCountEl) {
                const currentCount = parseInt(collectedCountEl.textContent) || 0;
                collectedCountEl.textContent = currentCount + 1;
            }
            
            // FIXED: Check if ALL pickups are collected
            setTimeout(() => {
                const allPickups = document.querySelectorAll('#pickup-list [data-donation-id]');
                const allCollected = Array.from(allPickups).every(card => {
                    const btn = card.querySelector('[id^="collect-btn-"]');
                    return btn && btn.textContent.includes('✓');
                });
                
                console.log('[v0] All collected?', allCollected, '- Total pickups:', allPickups.length);
                
                if (allCollected && allPickups.length > 0) {
                    // Hide map and show delivery button
                    const mapContainer = document.getElementById('pickup-map-container');
                    const infoBanner = document.getElementById('route-info-banner');
                    const deliveryBtn = document.getElementById('delivery-button-container');
                    
                    if (mapContainer) mapContainer.style.display = 'none';
                    if (infoBanner) infoBanner.style.display = 'none';
                    if (deliveryBtn) deliveryBtn.style.display = 'block';
                    
                    console.log('[v0] All items collected - showing delivery button');
                }
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
 * FIXED: Immediately removes item from DOM and refreshes map without full page reload
 * @param {number} donationId - ID of the donation to cancel
 */
function cancelPickup(donationId) {
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
    
    fetch(`/donation/cancel-pickup/${donationId}/`, {
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
            
            // FIXED: Immediately remove the card from DOM with animation
            if (pickupCard) {
                pickupCard.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
                pickupCard.style.opacity = '0';
                pickupCard.style.transform = 'translateX(-20px)';
                setTimeout(() => {
                    pickupCard.remove();
                    console.log('[v0] Pickup card removed from DOM');
                    
                    // FIXED: Update collected count if applicable
                    const collectedCountEl = document.getElementById('collected-count');
                    if (collectedCountEl) {
                        const currentCount = parseInt(collectedCountEl.textContent) || 0;
                        collectedCountEl.textContent = currentCount;
                    }
                    
                    // FIXED: Refresh the map with new route (without all pickups)
                    const remainingPickups = document.querySelectorAll('#pickup-list [data-donation-id]');
                    console.log('[v0] Remaining pickups:', remainingPickups.length);
                    
                    if (remainingPickups.length > 0) {
                        // Recalculate route without the cancelled item
                        setTimeout(() => {
                            calculateOptimizedRoute();
                        }, 300);
                    } else {
                        // No more pickups - hide map and delivery button
                        const mapContainer = document.getElementById('pickup-map-container');
                        const infoBanner = document.getElementById('route-info-banner');
                        const deliveryBtn = document.getElementById('delivery-button-container');
                        
                        if (mapContainer) mapContainer.style.display = 'none';
                        if (infoBanner) infoBanner.style.display = 'none';
                        if (deliveryBtn) deliveryBtn.style.display = 'none';
                        
                        console.log('[v0] No more pickups - hiding map');
                    }
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

// ============ CLEANUP ============
window.addEventListener('beforeunload', function() {
    stopLiveLocationTracking();
});
