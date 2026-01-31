# portal/utils/route_optimization.py
"""
Route optimization utilities for calculating efficient delivery routes using Traveling Salesman Problem (TSP) approximation.
"""

import math
from typing import List, Tuple, Dict
from geopy.distance import geodesic


class Location:
    """Represents a geographic location with coordinates and metadata"""
    def __init__(self, lat: float, lon: float, location_id: int | None = None, location_type: str = 'donation', name: str = ''):
        self.lat = lat
        self.lon = lon
        self.id = location_id
        self.type = location_type  # 'donation', 'restaurant', 'camp'
        self.name = name
    
    def distance_to(self, other: 'Location') -> float:
        """Calculate distance to another location in kilometers"""
        if not (self.lat and self.lon and other.lat and other.lon):
            return float('inf')
        return geodesic((self.lat, self.lon), (other.lat, other.lon)).km


class RouteOptimizer:
    """Optimizes pickup/delivery routes using nearest neighbor TSP approximation"""
    
    @staticmethod
    def nearest_neighbor_tsp(start: Location, locations: List[Location]) -> Tuple[List[Location], float]:
        """
        Nearest Neighbor TSP Algorithm - O(n²) approximation
        
        Args:
            start: Starting location (volunteer's current location)
            locations: List of locations to visit
        
        Returns:
            Tuple of (optimized_route, total_distance_km)
        """
        if not locations:
            return [start], 0.0
        
        # Filter out locations with invalid coordinates
        valid_locations = [loc for loc in locations if loc.lat and loc.lon]
        
        if not valid_locations:
            return [start], 0.0
        
        visited = set()
        current = start
        route = [current]
        total_distance = 0.0
        
        while len(visited) < len(valid_locations):
            # Find nearest unvisited location
            nearest = None
            nearest_distance = float('inf')
            
            for i, location in enumerate(valid_locations):
                if i not in visited:
                    distance = current.distance_to(location)
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest = (i, location)
            
            if nearest:
                visited.add(nearest[0])
                route.append(nearest[1])
                total_distance += nearest_distance
                current = nearest[1]
        
        return route, total_distance
    
    @staticmethod
    def calculate_route_with_destination(start: Location, pickups: List[Location], 
                                         destination: Location) -> Tuple[List[Location], float]:
        """
        Calculate optimized route from start → pickups → destination
        
        Args:
            start: Starting location (volunteer's location)
            pickups: List of pickup locations
            destination: Final destination (donation camp)
        
        Returns:
            Tuple of (optimized_route, total_distance_km)
        """
        if not pickups:
            return [start, destination], start.distance_to(destination)
        
        # Get optimized pickup order using nearest neighbor
        pickup_route, pickup_distance = RouteOptimizer.nearest_neighbor_tsp(start, pickups)
        
        # Add destination at the end
        final_route = pickup_route + [destination]
        
        # Calculate total distance
        total_distance = pickup_distance + pickup_route[-1].distance_to(destination)
        
        return final_route, total_distance
    
    @staticmethod
    def estimate_time_minutes(distance_km: float, avg_speed_kmh: float = 20, 
                              stops_count: int = 0, stop_duration_min: int = 5) -> int:
        """
        Estimate travel time including stops
        
        Args:
            distance_km: Total distance in kilometers
            avg_speed_kmh: Average speed (default 20 km/h for city traffic)
            stops_count: Number of stops
            stop_duration_min: Duration per stop in minutes
        
        Returns:
            Estimated time in minutes
        """
        travel_time = (distance_km / avg_speed_kmh) * 60  # Convert to minutes
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
