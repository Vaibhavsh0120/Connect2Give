/**
 * Real-time Geolocation Tracking for Connect2Give Volunteers
 * Uses Geolocation API (watchPosition) for continuous location updates
 */

class GeolocationTracker {
    constructor(options = {}) {
        this.watchId = null;
        this.currentMarker = null;
        this.map = options.map || null;
        this.onLocationChange = options.onLocationChange || null;
        this.onError = options.onError || null;
        this.updateCallback = options.updateCallback || null;
        
        // Geolocation options
        this.geolocationOptions = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0,
            ...options.geolocationOptions
        };
        
        // History tracking
        this.locationHistory = [];
        this.maxHistoryLength = 50;
    }
    
    /**
     * Start tracking volunteer's location
     */
    startTracking() {
        if (!navigator.geolocation) {
            console.error('[v0] Geolocation not supported');
            this._handleError({ message: 'Geolocation not supported on this device' });
            return false;
        }
        
        console.log('[v0] Starting geolocation tracking...');
        
        this.watchId = navigator.geolocation.watchPosition(
            (position) => this._handlePositionUpdate(position),
            (error) => this._handleLocationError(error),
            this.geolocationOptions
        );
        
        return this.watchId;
    }
    
    /**
     * Stop tracking volunteer's location
     */
    stopTracking() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
            console.log('[v0] Geolocation tracking stopped');
        }
    }
    
    /**
     * Handle position update
     */
    _handlePositionUpdate(position) {
        const { latitude, longitude, accuracy } = position.coords;
        const timestamp = new Date(position.timestamp);
        
        console.log(`[v0] Location: ${latitude.toFixed(6)}, ${longitude.toFixed(6)} (accuracy: ${accuracy.toFixed(0)}m)`);
        
        const locationData = {
            latitude,
            longitude,
            accuracy,
            timestamp
        };
        
        // Store in history
        this.locationHistory.push(locationData);
        if (this.locationHistory.length > this.maxHistoryLength) {
            this.locationHistory.shift();
        }
        
        // Update map marker if map exists
        if (this.map) {
            this._updateMapMarker(latitude, longitude);
        }
        
        // Call user-defined callback
        if (this.onLocationChange) {
            this.onLocationChange(locationData);
        }
        
        // Send update to server
        if (this.updateCallback) {
            this.updateCallback(locationData);
        }
    }
    
    /**
     * Handle geolocation errors
     */
    _handleLocationError(error) {
        let message = 'Unknown geolocation error';
        
        switch (error.code) {
            case error.PERMISSION_DENIED:
                message = 'Location permission denied. Please enable location services.';
                break;
            case error.POSITION_UNAVAILABLE:
                message = 'Location information unavailable.';
                break;
            case error.TIMEOUT:
                message = 'Location request timed out.';
                break;
        }
        
        console.error(`[v0] Geolocation error: ${message}`);
        this._handleError(error, message);
    }
    
    /**
     * Update map marker with current location
     */
    _updateMapMarker(lat, lon) {
        if (!this.map) return;
        
        const markerPosition = [lat, lon];
        
        // Remove old marker
        if (this.currentMarker) {
            this.map.removeLayer(this.currentMarker);
        }
        
        // Add new marker with smooth animation
        this.currentMarker = L.marker(markerPosition, {
            icon: L.icon({
                iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
                iconSize: [25, 41],
                shadowSize: [41, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34]
            }),
            title: 'Your Current Location'
        }).addTo(this.map);
        
        // Center map on marker
        this.map.panTo(markerPosition);
    }
    
    /**
     * Get current location (returns last known position)
     */
    getCurrentLocation() {
        if (this.locationHistory.length === 0) {
            return null;
        }
        return this.locationHistory[this.locationHistory.length - 1];
    }
    
    /**
     * Get location history
     */
    getLocationHistory() {
        return [...this.locationHistory];
    }
    
    /**
     * Clear location history
     */
    clearHistory() {
        this.locationHistory = [];
    }
    
    /**
     * Handle internal errors
     */
    _handleError(error, message = null) {
        if (this.onError) {
            this.onError(error, message);
        }
    }
    
    /**
     * Check if tracking is active
     */
    isTracking() {
        return this.watchId !== null;
    }
    
    /**
     * Get average speed (km/h) from location history
     */
    getAverageSpeed() {
        if (this.locationHistory.length < 2) {
            return 0;
        }
        
        let totalDistance = 0;
        let totalTime = 0;
        
        for (let i = 1; i < this.locationHistory.length; i++) {
            const prev = this.locationHistory[i - 1];
            const curr = this.locationHistory[i];
            
            // Calculate distance
            const R = 6371; // Earth's radius in km
            const dLat = this._toRad(curr.latitude - prev.latitude);
            const dLon = this._toRad(curr.longitude - prev.longitude);
            const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                      Math.cos(this._toRad(prev.latitude)) * Math.cos(this._toRad(curr.latitude)) *
                      Math.sin(dLon / 2) * Math.sin(dLon / 2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
            const distance = R * c;
            
            // Calculate time in hours
            const time = (curr.timestamp - prev.timestamp) / (1000 * 3600);
            
            totalDistance += distance;
            totalTime += time;
        }
        
        return totalTime > 0 ? totalDistance / totalTime : 0;
    }
    
    /**
     * Convert degrees to radians
     */
    _toRad(degrees) {
        return degrees * (Math.PI / 180);
    }
}

/**
 * Initialize geolocation tracker with map
 */
function initializeGeolocationTracker(mapElement, volunteerId = null) {
    console.log('[v0] Initializing geolocation tracker');
    
    // Initialize map if not exists
    let map = null;
    if (mapElement) {
        map = L.map(mapElement).setView([28.6448, 77.2167], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    }
    
    // Create tracker
    const tracker = new GeolocationTracker({
        map: map,
        onLocationChange: (location) => {
            console.log('[v0] Location updated', location);
            updateLocationDisplay(location);
        },
        onError: (error, message) => {
            console.error('[v0] Tracking error:', message);
            showGeolocationError(message);
        },
        updateCallback: (location) => {
            // Send update to server via API if needed
            if (volunteerId) {
                fetch('/api/update-volunteer-location/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        latitude: location.latitude,
                        longitude: location.longitude,
                        accuracy: location.accuracy
                    })
                }).catch(err => console.error('[v0] Failed to send location:', err));
            }
        }
    });
    
    return tracker;
}

/**
 * Update location display (updates HTML elements)
 */
function updateLocationDisplay(location) {
    const latElement = document.getElementById('current-latitude');
    const lonElement = document.getElementById('current-longitude');
    const accuracyElement = document.getElementById('location-accuracy');
    const timeElement = document.getElementById('location-time');
    
    if (latElement) latElement.textContent = location.latitude.toFixed(6);
    if (lonElement) lonElement.textContent = location.longitude.toFixed(6);
    if (accuracyElement) accuracyElement.textContent = location.accuracy.toFixed(0) + 'm';
    if (timeElement) timeElement.textContent = new Date(location.timestamp).toLocaleTimeString();
}

/**
 * Show geolocation error message
 */
function showGeolocationError(message) {
    console.error('[v0] Error:', message);
    // You can display this error in a toast or modal
    if (typeof showToast === 'function') {
        showToast(message, 'error');
    }
}

/**
 * Get CSRF token from cookies
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { GeolocationTracker, initializeGeolocationTracker };
}
