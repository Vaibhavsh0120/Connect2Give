/**
 * Volunteer Deliveries Management
 * Handles delivery map initialization and delivery confirmations
 * Separate from pickups to ensure clean separation of concerns
 */

let deliveryMapInstance = null;
let deliveryRoutingControl = null;
let volunteerDeliveryMarker = null;
let currentVolunteerPosition = null;
let liveTrackingWatchId = null;

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

// ============ PAGE INITIALIZATION ============
document.addEventListener('DOMContentLoaded', function () {
    // Initialize delivery map
    initializeDeliveryMap();
    
    // Start live location tracking
    startLiveLocationTracking();
});

// ============ ACTIONS ============

/**
 * Handle delivery confirmation via AJAX to avoid black JSON page
 */
window.confirmDelivery = function(campId) {
    if (!confirm('Are you sure you want to mark these items as delivered?')) {
        return;
    }

    const btn = document.querySelector('button[data-testid="confirm-delivery-btn"]');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = 'Processing...';
    }

    const csrftoken = getCookie('csrftoken');

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
            // Redirect to history tab to show the pending verifications
            window.location.href = '/dashboard/volunteer/deliveries/?tab=history';
        } else {
            alert(data.message || 'Error processing delivery.');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = 'Confirm & Mark All as Delivered';
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An unexpected error occurred.');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = 'Confirm & Mark All as Delivered';
        }
    });
};

// ============ DELIVERY MAP INITIALIZATION ============

/**
 * Initialize the delivery map showing route to nearest camp
 */
function initializeDeliveryMap() {
    const mapContainer = document.getElementById('delivery-map');
    const campDataEl = document.getElementById('nearest-camp-data');
    const volunteerDataEl = document.getElementById('volunteer-location-data');
    
    if (!mapContainer) {
        console.error('[v0] Delivery map container not found');
        return;
    }
    
    if (!campDataEl) {
        mapContainer.innerHTML = '<p class="empty-state">No active camps found. Please register with an NGO first.</p>';
        return;
    }
    
    let campData, volunteerData;
    
    try {
        campData = JSON.parse(campDataEl.textContent);
        volunteerData = volunteerDataEl ? JSON.parse(volunteerDataEl.textContent) : null;
    } catch (e) {
        console.error('[v0] Error parsing map data:', e);
        mapContainer.innerHTML = '<p class="empty-state">Error loading map data. Please refresh the page.</p>';
        return;
    }
    
    // Get volunteer location (GPS > profile > default)
    let volunteerLat = 28.6448;
    let volunteerLon = 77.2167;
    
    if (currentVolunteerPosition) {
        volunteerLat = currentVolunteerPosition.lat;
        volunteerLon = currentVolunteerPosition.lon;
    } else if (volunteerData && volunteerData.lat && volunteerData.lon) {
        volunteerLat = volunteerData.lat;
        volunteerLon = volunteerData.lon;
    }
    
    // Clean up existing map
    if (deliveryMapInstance) {
        deliveryMapInstance.remove();
        deliveryMapInstance = null;
    }
    
    // Initialize map
    deliveryMapInstance = L.map('delivery-map', {
        zoomControl: true,
        attributionControl: false
    }).setView([volunteerLat, volunteerLon], 14);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(deliveryMapInstance);
    
    // Force map to recalculate size after container is visible
    setTimeout(() => {
        deliveryMapInstance.invalidateSize();
        
        // Fit bounds after invalidateSize
        deliveryMapInstance.fitBounds([
            [volunteerLat, volunteerLon],
            [campData.latitude, campData.longitude]
        ], { padding: [50, 50] });
    }, 200);
    
    // Add volunteer marker
    volunteerDeliveryMarker = L.marker([volunteerLat, volunteerLon], { 
        icon: bikeIcon, 
        zIndexOffset: 1000 
    }).addTo(deliveryMapInstance).bindPopup('<strong>Your Location</strong>');
    
    // Add camp marker
    L.marker([campData.latitude, campData.longitude], { 
        icon: campIcon 
    }).addTo(deliveryMapInstance).bindPopup(
        `<strong>${campData.name}</strong><br>${campData.ngo_name}<br><small>${campData.address}</small>`
    );
    
    // Add routing with road path if available
    if (typeof L.Routing !== 'undefined') {
        deliveryRoutingControl = L.Routing.control({
            waypoints: [
                L.latLng(volunteerLat, volunteerLon),
                L.latLng(campData.latitude, campData.longitude)
            ],
            routeWhileDragging: false,
            show: false,
            addWaypoints: false,
            createMarker: function() { 
                return null; // Use custom markers instead
            },
            lineOptions: {
                styles: [{ color: '#10b981', weight: 5, opacity: 0.8 }],
                addWaypoints: false
            }
        }).addTo(deliveryMapInstance);
        
        // Update distance and time when route is found
        deliveryRoutingControl.on('routesfound', function(e) {
            if (e.routes && e.routes[0]) {
                const summary = e.routes[0].summary;
                const distance = (summary.totalDistance / 1000).toFixed(2);
                const time = Math.round(summary.totalTime / 60);
                
                // Update route summary
                updateDeliveryRouteSummary(distance, time, campData);
            }
        });
    } else {
        // Fallback: Draw simple polyline without routing
        L.polyline([
            [volunteerLat, volunteerLon],
            [campData.latitude, campData.longitude]
        ], { color: '#10b981', weight: 4, opacity: 0.8 }).addTo(deliveryMapInstance);
        
        // Show static route summary
        updateDeliveryRouteSummaryFallback(campData);
    }
}

/**
 * Update delivery route summary with road distance and time
 */
function updateDeliveryRouteSummary(distance, time, campData) {
    const deliveryInfo = document.getElementById('delivery-info');
    
    if (!deliveryInfo) return;
    
    deliveryInfo.innerHTML = `
        <div class="route-summary">
            <div style="flex: 1;">
                <p><strong>Distance:</strong> ${distance} km</p>
                <p><strong>Estimated Time:</strong> ${time} minutes</p>
                <p><strong>Destination:</strong> <strong>${campData.name}</strong> (${campData.ngo_name})</p>
            </div>
            <div>
                <button type="button" class="btn-primary-action" data-testid="confirm-delivery-btn" onclick="confirmDelivery(${campData.pk})">
                    Confirm & Mark All as Delivered
                </button>
            </div>
        </div>
    `;
}

/**
 * Fallback: Update delivery summary without routing library
 */
function updateDeliveryRouteSummaryFallback(campData) {
    const deliveryInfo = document.getElementById('delivery-info');
    
    if (!deliveryInfo) return;
    
    deliveryInfo.innerHTML = `
        <div class="route-summary">
            <div style="flex: 1;">
                <p><strong>Destination:</strong> <strong>${campData.name}</strong> (${campData.ngo_name})</p>
                <p><small>Location services unavailable. Map is showing your route.</small></p>
            </div>
            <div>
                <button type="button" class="btn-primary-action" data-testid="confirm-delivery-btn" onclick="confirmDelivery(${campData.pk})">
                    Confirm & Mark All as Delivered
                </button>
            </div>
        </div>
    `;
}

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
            
            // Update volunteer marker on map
            if (volunteerDeliveryMarker) {
                volunteerDeliveryMarker.setLatLng([latitude, longitude]);
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

// ============ CLEANUP ============
window.addEventListener('beforeunload', function() {
    stopLiveLocationTracking();
});