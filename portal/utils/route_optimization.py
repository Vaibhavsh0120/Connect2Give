# portal/utils/route_optimization.py
"""
Route optimization utilities for calculating efficient delivery routes.
Supports Google Maps Distance Matrix API with fallback to geodesic calculations.
"""

import math
import requests
from typing import List, Tuple, Dict, Optional
from geopy.distance import geodesic
from django.conf import settings


class Location:
    """Represents a geographic location with coordinates and metadata"""
    def __init__(self, lat: float, lon: float, location_id: Optional[int] = None, 
                 location_type: str = 'donation', name: str = ''):
        self.lat = lat
        self.lon = lon
        self.id = location_id
        self.type = location_type  # 'donation', 'restaurant', 'camp', 'volunteer'
        self.name = name
    
    def distance_to(self, other: 'Location') -> float:
        """Calculate geodesic distance to another location in kilometers (fallback)"""
        if not (self.lat and self.lon and other.lat and other.lon):
            return float('inf')
        return geodesic((self.lat, self.lon), (other.lat, other.lon)).km
    
    def to_coords_string(self) -> str:
        """Return coordinates as string for Google Maps API"""
        return f"{self.lat},{self.lon}"


class GoogleMapsService:
    """Service for interacting with Google Maps Distance Matrix API"""
    
    BASE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key: str = api_key or getattr(settings, 'GOOGLE_MAPS_API_KEY', '') or ''
        self._api_available = bool(self.api_key)
    
    def is_available(self) -> bool:
        """Check if Google Maps API is configured"""
        return self._api_available
    
    def get_distance_matrix(self, origins: List[Location], destinations: List[Location],
                           mode: str = 'driving', traffic_model: str = 'best_guess') -> Optional[Dict]:
        """
        Fetch distance matrix from Google Maps API
        
        Args:
            origins: List of origin locations
            destinations: List of destination locations
            mode: Travel mode (driving, walking, bicycling)
            traffic_model: Traffic model for ETA (best_guess, pessimistic, optimistic)
        
        Returns:
            Dictionary with distances and durations, or None if API call fails
        """
        if not self.is_available():
            return None
        
        try:
            # Build origin and destination strings
            origins_str = '|'.join([loc.to_coords_string() for loc in origins])
            destinations_str = '|'.join([loc.to_coords_string() for loc in destinations])
            
            params = {
                'origins': origins_str,
                'destinations': destinations_str,
                'mode': mode,
                'traffic_model': traffic_model,
                'departure_time': 'now',  # For live traffic data
                'key': self.api_key
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'OK':
                print(f"[v0] Google Maps API error: {data.get('status')}")
                return None
            
            return self._parse_distance_matrix(data, origins, destinations)
            
        except requests.RequestException as e:
            print(f"[v0] Google Maps API request failed: {e}")
            return None
        except Exception as e:
            print(f"[v0] Error processing Google Maps response: {e}")
            return None
    
    def _parse_distance_matrix(self, data: Dict, origins: List[Location], 
                               destinations: List[Location]) -> Dict:
        """Parse Google Maps API response into usable format"""
        result = {
            'distances': [],  # Distance in km
            'durations': [],  # Duration in minutes
            'raw': data
        }
        
        for i, row in enumerate(data.get('rows', [])):
            distance_row = []
            duration_row = []
            
            for j, element in enumerate(row.get('elements', [])):
                if element.get('status') == 'OK':
                    # Distance in meters -> convert to km
                    distance_m = element.get('distance', {}).get('value', 0)
                    distance_km = distance_m / 1000
                    
                    # Duration in seconds -> convert to minutes
                    # Use duration_in_traffic if available for live traffic data
                    duration_s = element.get('duration_in_traffic', element.get('duration', {})).get('value', 0)
                    duration_min = duration_s / 60
                    
                    distance_row.append(distance_km)
                    duration_row.append(duration_min)
                else:
                    # If route not found, use fallback geodesic distance
                    fallback_dist = origins[i].distance_to(destinations[j])
                    fallback_time = fallback_dist / 20 * 60  # Assume 20 km/h average
                    distance_row.append(fallback_dist)
                    duration_row.append(fallback_time)
            
            result['distances'].append(distance_row)
            result['durations'].append(duration_row)
        
        return result
    
    def get_single_route(self, origin: Location, destination: Location, 
                        mode: str = 'driving') -> Optional[Dict]:
        """Get distance and duration for a single route"""
        matrix = self.get_distance_matrix([origin], [destination], mode)
        if matrix and matrix['distances'] and matrix['durations']:
            return {
                'distance_km': matrix['distances'][0][0],
                'duration_minutes': matrix['durations'][0][0]
            }
        return None


class RouteOptimizer:
    """Optimizes pickup/delivery routes using Google Maps API or geodesic fallback"""
    
    def __init__(self, use_google_maps: bool = True):
        self.google_maps: Optional[GoogleMapsService] = GoogleMapsService() if use_google_maps else None
        self._use_google_maps = use_google_maps and self.google_maps is not None and self.google_maps.is_available()
    
    def nearest_neighbor_tsp(self, start: Location, locations: List[Location]) -> Tuple[List[Location], float, float]:
        """
        Nearest Neighbor TSP Algorithm with optional Google Maps integration
        
        Args:
            start: Starting location (volunteer's current location)
            locations: List of locations to visit
        
        Returns:
            Tuple of (optimized_route, total_distance_km, total_time_minutes)
        """
        if not locations:
            return [start], 0.0, 0.0
        
        # Filter out locations with invalid coordinates
        valid_locations = [loc for loc in locations if loc.lat and loc.lon]
        
        if not valid_locations:
            return [start], 0.0, 0.0
        
        # Try to get distance matrix from Google Maps
        distance_matrix = None
        duration_matrix = None
        
        if self._use_google_maps and self.google_maps is not None:
            all_locations = [start] + valid_locations
            matrix_result = self.google_maps.get_distance_matrix(all_locations, all_locations)
            
            if matrix_result:
                distance_matrix = matrix_result['distances']
                duration_matrix = matrix_result['durations']
                print(f"[v0] Using Google Maps road distances for TSP optimization")
        
        # Perform nearest neighbor algorithm
        visited = set()
        current_index = 0  # Start location is index 0
        route = [start]
        total_distance = 0.0
        total_time = 0.0
        
        while len(visited) < len(valid_locations):
            nearest = None
            nearest_distance = float('inf')
            nearest_time = 0
            
            for i, location in enumerate(valid_locations):
                if i not in visited:
                    if distance_matrix:
                        # Use Google Maps distances (index offset by 1 for valid_locations)
                        distance = distance_matrix[current_index][i + 1]
                        time = duration_matrix[current_index][i + 1]
                    else:
                        # Fallback to geodesic distance
                        current_loc = route[-1]
                        distance = current_loc.distance_to(location)
                        time = distance / 20 * 60  # Assume 20 km/h
                    
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_time = time
                        nearest = (i, location)
            
            if nearest:
                visited.add(nearest[0])
                route.append(nearest[1])
                total_distance += nearest_distance
                total_time += nearest_time
                current_index = nearest[0] + 1  # Update index for matrix lookup
        
        return route, total_distance, total_time
    
    def calculate_route_with_destination(self, start: Location, pickups: List[Location], 
                                         destination: Location) -> Tuple[List[Location], float, float]:
        """
        Calculate optimized route from start -> pickups -> destination
        
        Args:
            start: Starting location (volunteer's location)
            pickups: List of pickup locations
            destination: Final destination (donation camp)
        
        Returns:
            Tuple of (optimized_route, total_distance_km, total_time_minutes)
        """
        if not pickups:
            # Direct route to destination
            if self._use_google_maps and self.google_maps is not None:
                route_data = self.google_maps.get_single_route(start, destination)
                if route_data:
                    return [start, destination], route_data['distance_km'], route_data['duration_minutes']
            
            # Fallback
            distance = start.distance_to(destination)
            time = distance / 20 * 60
            return [start, destination], distance, time
        
        # Get optimized pickup order using nearest neighbor
        pickup_route, pickup_distance, pickup_time = self.nearest_neighbor_tsp(start, pickups)
        
        # Calculate distance from last pickup to destination
        last_pickup = pickup_route[-1]
        
        if self._use_google_maps and self.google_maps is not None:
            final_leg = self.google_maps.get_single_route(last_pickup, destination)
            if final_leg:
                final_distance = final_leg['distance_km']
                final_time = final_leg['duration_minutes']
            else:
                final_distance = last_pickup.distance_to(destination)
                final_time = final_distance / 20 * 60
        else:
            final_distance = last_pickup.distance_to(destination)
            final_time = final_distance / 20 * 60
        
        # Build final route
        final_route = pickup_route + [destination]
        total_distance = pickup_distance + final_distance
        total_time = pickup_time + final_time
        
        return final_route, total_distance, total_time
    
    def find_nearest_location(self, origin: Location, locations: List[Location]) -> Tuple[Optional[Location], float, float]:
        """
        Find the nearest location using road distance (or geodesic fallback)
        
        Args:
            origin: Starting location
            locations: List of candidate locations
        
        Returns:
            Tuple of (nearest_location, distance_km, duration_minutes)
        """
        if not locations:
            return None, float('inf'), 0.0
        
        valid_locations = [loc for loc in locations if loc.lat and loc.lon]
        if not valid_locations:
            return None, float('inf'), 0.0
        
        # Try Google Maps for accurate road distances
        if self._use_google_maps and self.google_maps is not None:
            matrix = self.google_maps.get_distance_matrix([origin], valid_locations)
            
            if matrix and matrix['distances'] and matrix['distances'][0]:
                min_idx = 0
                min_distance = float('inf')
                
                for i, dist in enumerate(matrix['distances'][0]):
                    if dist < min_distance:
                        min_distance = dist
                        min_idx = i
                
                return (
                    valid_locations[min_idx],
                    min_distance,
                    matrix['durations'][0][min_idx]
                )
        
        # Fallback to geodesic distance
        nearest = None
        min_distance = float('inf')
        
        for location in valid_locations:
            distance = origin.distance_to(location)
            if distance < min_distance:
                min_distance = distance
                nearest = location
        
        duration = min_distance / 20 * 60 if min_distance < float('inf') else 0
        return nearest, min_distance, duration
    
    @staticmethod
    def estimate_time_minutes(distance_km: float, avg_speed_kmh: float = 20, 
                              stops_count: int = 0, stop_duration_min: int = 5) -> int:
        """
        Estimate travel time including stops (fallback method)
        
        Args:
            distance_km: Total distance in kilometers
            avg_speed_kmh: Average speed (default 20 km/h for city traffic)
            stops_count: Number of stops
            stop_duration_min: Duration per stop in minutes
        
        Returns:
            Estimated time in minutes
        """
        travel_time = (distance_km / avg_speed_kmh) * 60
        stop_time = stops_count * stop_duration_min
        return int(travel_time + stop_time)


def build_route_map_data(route: List[Location]) -> List[Dict]:
    """
    Convert route locations to map-friendly format
    
    Args:
        route: List of Location objects
    
    Returns:
        List of dictionaries with lat, lon, name, type, id
    """
    return [
        {
            'lat': location.lat,
            'lon': location.lon,
            'name': location.name,
            'type': location.type,
            'id': location.id
        }
        for location in route
    ]


# Convenience function for backward compatibility
def get_route_optimizer(use_google_maps: bool = True) -> RouteOptimizer:
    """Get a configured RouteOptimizer instance"""
    return RouteOptimizer(use_google_maps=use_google_maps)
