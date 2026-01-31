/**
 * Volunteer Pickups & Delivery Management
 * Handles donation acceptance, delivery routing, live tracking, and map display
 */

let deliveryMapInstance = null;
let liveTrackingWatchId = null;
let volunteerMarker = null;
let routePolyline = null;

// Custom bike/scooter icon for volunteer marker
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

/**
 * Initialize the page when DOM is ready
 */
document.addEventListener('DOMContentLoaded', function () {
    const currentView = document.body.dataset.currentView || '';
    
    if (currentView === "delivery_route") {
        initializeDeliveryRouteMap();
    }

    // Tab navigation from URL
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('view') === 'history') {
        const mainContent = document.getElementById('main-content');
        const historyContent = document.getElementById('history');
        
        if (mainContent) mainContent.classList.remove('active');
        if (historyContent) historyContent.classList.add('active');
    }
});

/**
 * Initialize the delivery route map with Leaflet, routing, and live tracking
 */
function initializeDeliveryRouteMap() {
    const volunteerDataElement = document.getElementById('volunteer-location-data');
    const campDataElement = document.getElementById('nearest-camp-data');
    const mapContainer = document.getElementById('delivery-map');

    if (!volunteerDataElement || !mapContainer || !campDataElement) {
        if (mapContainer) {
            mapContainer.innerHTML = '<p class="empty-state">Cannot display route due to missing location data. Please set your location in your profile.</p>';
        }
        return;
    }

    if (typeof L === 'undefined' || typeof L.Routing === 'undefined') {
        mapContainer.innerHTML = '<p class="empty-state">Error: Mapping library failed to load. Please refresh the page.</p>';
        return;
    }

    const volunteerData = JSON.parse(volunteerDataElement.textContent);
    const campData = JSON.parse(campDataElement.textContent);

    // Initialize map
    deliveryMapInstance = L.map('delivery-map', {
        zoomControl: false,
        attributionControl: false
    }).setView([volunteerData.lat, volunteerData.lon], 14);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(deliveryMapInstance);
    
    const csrftoken = getCookie('csrftoken');
    const deliveryFormAction = `/donation/deliver/to/${campData.pk}/`;

    // Add routing control with road path
    const routingControl = L.Routing.control({
        waypoints: [
            L.latLng(volunteerData.lat, volunteerData.lon),
            L.latLng(campData.latitude, campData.longitude)
        ],
        routeWhileDragging: false,
        show: false,
        addWaypoints: false,
        createMarker: (i, waypoint) => {
            if (i === 0) {
                // Volunteer marker - will be updated by live tracking
                volunteerMarker = L.marker(waypoint.latLng, { 
                    icon: bikeIcon,
                    zIndexOffset: 1000
                }).bindPopup("<strong>Your Location</strong>");
                return volunteerMarker;
            } else {
                // Camp marker
                return L.marker(waypoint.latLng, { draggable: false })
                    .bindPopup(`<strong>${campData.name}</strong><br>${campData.ngo_name}<br><small>${campData.address}</small>`);
            }
        },
        lineOptions: {
            styles: [{ color: '#10b981', weight: 5, opacity: 0.8 }]
        }
    })
    .on('routesfound', function(e) {
        const summary = e.routes[0].summary;
        const distance = (summary.totalDistance / 1000).toFixed(2);
        const time = Math.round(summary.totalTime / 60);
        
        // Store route coordinates for polyline updates
        routePolyline = e.routes[0].coordinates;
        
        const deliveryInfo = document.getElementById('delivery-info');
        if (deliveryInfo) {
            deliveryInfo.innerHTML = `
                <div class="route-summary">
                    <p><strong>Distance:</strong> ${distance} km</p>
                    <p><strong>ETA:</strong> ${time} minutes</p>
                </div>
            `;
        }
    })
    .addTo(deliveryMapInstance);
    
    // Start live tracking
    startLiveLocationTracking(deliveryMapInstance, campData);
}

/**
 * Start live location tracking using watchPosition
 * @param {L.Map} map - Leaflet map instance
 * @param {Object} campData - Camp destination data
 */
function startLiveLocationTracking(map, campData) {
    if (!navigator.geolocation) {
        console.error('[v0] Geolocation not supported');
        return;
    }
    
    console.log('[v0] Starting live location tracking...');
    
    const trackingIndicator = document.getElementById('delivery-live-tracking') || document.getElementById('live-tracking-status');
    if (trackingIndicator) {
        trackingIndicator.style.display = 'flex';
    }
    
    liveTrackingWatchId = navigator.geolocation.watchPosition(
        (position) => {
            const { latitude, longitude, accuracy } = position.coords;
            console.log(`[v0] Live position: ${latitude.toFixed(6)}, ${longitude.toFixed(6)} (accuracy: ${accuracy.toFixed(0)}m)`);
            
            // Update volunteer marker position with smooth animation
            if (volunteerMarker) {
                volunteerMarker.setLatLng([latitude, longitude]);
            } else if (map) {
                volunteerMarker = L.marker([latitude, longitude], { 
                    icon: bikeIcon,
                    zIndexOffset: 1000
                }).addTo(map).bindPopup("<strong>Your Location</strong>");
            }
            
            // Calculate and update live ETA
            if (campData) {
                updateLiveETA(latitude, longitude, campData.latitude, campData.longitude);
            }
            
            // Send location update to server
            sendLocationUpdate(latitude, longitude, accuracy);
        },
        (error) => {
            console.error('[v0] Geolocation error:', error.message);
            let message = 'Location tracking error';
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    message = 'Please enable location access for live tracking';
                    break;
                case error.POSITION_UNAVAILABLE:
                    message = 'Location unavailable';
                    break;
                case error.TIMEOUT:
                    message = 'Location request timed out';
                    break;
            }
            if (typeof showToast === 'function') {
                showToast(message, 'warning');
            }
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 5000
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
        console.log('[v0] Live tracking stopped');
    }
}

/**
 * Update live ETA based on current position
 */
function updateLiveETA(currentLat, currentLon, destLat, destLon) {
    // Calculate straight-line distance (approximation)
    const R = 6371; // Earth's radius in km
    const dLat = (destLat - currentLat) * Math.PI / 180;
    const dLon = (destLon - currentLon) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(currentLat * Math.PI / 180) * Math.cos(destLat * Math.PI / 180) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distance = R * c;
    
    // Estimate time at 20 km/h average city speed
    const etaMinutes = Math.round((distance / 20) * 60);
    
    // Update display
    const etaElement = document.querySelector('.route-detail-value');
    if (etaElement && etaElement.parentElement) {
        const label = etaElement.parentElement.querySelector('.route-detail-label');
        if (label && label.textContent.includes('Time')) {
            etaElement.textContent = etaMinutes;
        }
    }
}

/**
 * Send location update to server
 */
function sendLocationUpdate(latitude, longitude, accuracy) {
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
    }).catch(err => console.error('[v0] Failed to send location update:', err));
}

/**
 * Accept a donation via AJAX
 * @param {number} donationId - ID of the donation to accept
 */
function acceptDonation(donationId) {
    const csrftoken = getCookie('csrftoken');
    const acceptBtn = document.getElementById(`accept-btn-${donationId}`);
    
    if (!acceptBtn) {
        console.error('Accept button not found for donation:', donationId);
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
            
            setTimeout(() => {
                const row = document.getElementById(`donation-row-${donationId}`);
                if (row) {
                    row.style.transition = 'opacity 0.3s ease-out';
                    row.style.opacity = '0';
                    setTimeout(() => row.remove(), 300);
                }
            }, 1000);
            
            showToast(data.message || 'Donation accepted! Please pick it up within 30 minutes.', 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            acceptBtn.disabled = false;
            acceptBtn.textContent = 'Accept';
            acceptBtn.style.cursor = 'pointer';
            showToast(data.message || 'Failed to accept donation', 'error');
        }
    })
    .catch(error => {
        console.error('Error accepting donation:', error);
        acceptBtn.disabled = false;
        acceptBtn.textContent = 'Accept';
        acceptBtn.style.cursor = 'pointer';
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Mark a donation as collected via AJAX
 * @param {number} donationId - ID of the donation to mark as collected
 */
function markAsCollected(donationId) {
    const csrftoken = getCookie('csrftoken');
    const collectBtn = document.getElementById(`collect-btn-${donationId}`);

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
            showToast(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            collectBtn.disabled = false;
            collectBtn.textContent = 'Mark as Collected';
            showToast(data.message || 'Failed to update status', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        collectBtn.disabled = false;
        collectBtn.textContent = 'Mark as Collected';
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Register with an NGO via AJAX
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
            setTimeout(() => location.reload(), 1500);
        } else {
            registerBtn.disabled = false;
            registerBtn.textContent = 'Register';
            showToast(data.message || 'Failed to register', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        registerBtn.disabled = false;
        registerBtn.textContent = 'Register';
        showToast('An error occurred. Please try again.', 'error');
    });
}

/**
 * Unregister from an NGO via AJAX
 * @param {number} ngoId - ID of the NGO to unregister from
 */
function unregisterFromNGO(ngoId) {
    if (!confirm('Are you sure you want to unregister from this NGO?')) {
        return;
    }
    
    const csrftoken = getCookie('csrftoken');
    const unregisterBtn = document.getElementById(`unregister-btn-${ngoId}`);
    
    if (unregisterBtn) {
        unregisterBtn.disabled = true;
        unregisterBtn.textContent = 'Unregistering...';
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
            setTimeout(() => location.reload(), 1500);
        } else {
            if (unregisterBtn) {
                unregisterBtn.disabled = false;
                unregisterBtn.textContent = 'Unregister';
            }
            showToast(data.message || 'Failed to unregister', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        if (unregisterBtn) {
            unregisterBtn.disabled = false;
            unregisterBtn.textContent = 'Unregister';
        }
        showToast('An error occurred. Please try again.', 'error');
    });
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    stopLiveLocationTracking();
});
