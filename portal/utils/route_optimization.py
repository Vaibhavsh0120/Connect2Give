# portal/utils/route_optimization.py
"""
Route optimization utilities for calculating efficient delivery routes.
Uses geodesic distance calculations and Leaflet Routing Machine for web-based routing.
No external API keys required - completely free and open-source solution.
"""

import math
from typing import List, Tuple, Dict, Optional
from geopy.distance import geodesic


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
        """Calculate geodesic distance to another location in kilometers"""
        if not (self.lat and self.lon and other.lat and other.lon):
            return float('inf')
        return geodesic((self.lat, self.lon), (other.lat, other.lon)).km
    
    def to_coords_string(self) -> str:
        """Return coordinates as string"""
        return f"{self.lat},{self.lon}"


class RouteOptimizer:
    """Optimizes pickup/delivery routes using geodesic distance calculations"""
    
    def __init__(self, use_google_maps: bool = True):
        # use_google_maps parameter kept for backward compatibility but ignored
        # Now always uses free geodesic calculations
        pass
    
    def nearest_neighbor_tsp(self, start: Location, locations: List[Location]) -> Tuple[List[Location], float, float]:
        """
        Nearest Neighbor TSP Algorithm using geodesic distances
        
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
        
        print(f"[v0] Optimizing route for {len(valid_locations)} stops using geodesic distances")
        
        # Perform nearest neighbor algorithm with geodesic distances
        visited = set()
        route = [start]
        total_distance = 0.0
        total_time = 0.0
        
        while len(visited) < len(valid_locations):
            nearest = None
            nearest_distance = float('inf')
            nearest_time = 0
            
            for i, location in enumerate(valid_locations):
                if i not in visited:
                    current_loc = route[-1]
                    distance = current_loc.distance_to(location)
                    time = distance / 20 * 60  # Assume 20 km/h average speed
                    
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_time = time
                        nearest = (i, location)
            
            if nearest:
                visited.add(nearest[0])
                route.append(nearest[1])
                total_distance += nearest_distance
                total_time += nearest_time
        
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
            distance = start.distance_to(destination)
            time = distance / 20 * 60
            return [start, destination], distance, time
        
        # Get optimized pickup order using nearest neighbor
        pickup_route, pickup_distance, pickup_time = self.nearest_neighbor_tsp(start, pickups)
        
        # Calculate distance from last pickup to destination
        last_pickup = pickup_route[-1]
        final_distance = last_pickup.distance_to(destination)
        final_time = final_distance / 20 * 60
        
        # Build final route
        final_route = pickup_route + [destination]
        total_distance = pickup_distance + final_distance
        total_time = pickup_time + final_time
        
        return final_route, total_distance, total_time
    
    def find_nearest_location(self, origin: Location, locations: List[Location]) -> Tuple[Optional[Location], float, float]:
        """
        Find the nearest location using geodesic distances
        
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
        
        # Find nearest using geodesic distance
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
