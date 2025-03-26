from math import ceil
import os
import requests
from datetime import timedelta
from django.utils import timezone 

from .models import DailyLog, DutyStatus, LogSheet

def calculate_route(pickup, dropoff):
    # api_key = "sk.eyJ1Ijoic2ltb24td2pyIiwiYSI6ImNtOGxta3BybjE3MWgycXNlb2xrendnaXYifQ.WIDwmQfquYKcdM2gdgqTGw"
    API_KEY=os.getenv("MAP_BOX_API_KEY")
    pickup_coords = geocode_city(pickup)
    dropoff_coords = geocode_city(dropoff)
    url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{pickup_coords};{dropoff_coords}?access_token={API_KEY}&geometries=geojson"
    print("Making the map request")
    response = requests.get(url, verify=False)
    if response.status_code == 200:
        print("success map response")
        route_data = response.json()        

        return {
            'distance_miles': route_data['routes'][0]['distance'] * 0.000621371,
            'geometry': route_data['routes'][0]['geometry'],
            'stops': [
                {'type': 'pickup', 'coordinates': route_data['routes'][0]['geometry']['coordinates'][0]},
                {'type': 'dropoff', 'coordinates': route_data['routes'][0]['geometry']['coordinates'][-1]}
            ],
            'fuel_stops': calculate_fuel_stops(route_data),
            'rests': calculate_rests(route_data) 
        }
    return None

def calculate_fuel_stops(route_data):
    """Calculate fueling stops every 1000 miles"""
    fuel_stops = []
    total_distance = route_data['routes'][0]['distance'] * 0.000621371  # meters to miles
    interval = 1000  # miles
    
    for i in range(1, int(total_distance // interval) + 1):
        idx = min(i * 100, len(route_data['routes'][0]['geometry']['coordinates']) - 1)
        fuel_stops.append({
            'type': 'fuel',
            'coordinates': route_data['routes'][0]['geometry']['coordinates'][idx]
        })
    
    return fuel_stops

def geocode_city(city_name):
    api_key = "sk.eyJ1Ijoic2ltb24td2pyIiwiYSI6ImNtOGxta3BybjE3MWgycXNlb2xrendnaXYifQ.WIDwmQfquYKcdM2gdgqTGw"
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{city_name}.json?access_token={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['features']:
            longitude, latitude = data['features'][0]['center']
            return f"{longitude},{latitude}"
    return None

def calculate_stops(route_data):
    """
    Calculate stops along the route (e.g., pickup and dropoff locations).
    """
    stops = [
        {"type": "stop", "coordinates": route_data['routes'][0]['geometry']['coordinates'][0], "description": "Pickup Location"},
        {"type": "stop", "coordinates": route_data['routes'][0]['geometry']['coordinates'][-1], "description": "Dropoff Location"},
    ]
    return stops

def calculate_rests(route_data):
    """
    Calculate rest locations along the route.
    """
    rests = []
    coordinates = route_data['routes'][0]['geometry']['coordinates']
    total_duration = route_data['routes'][0]['duration']  # Duration in seconds

    # an assumption I am making; Add a rest stop every 4 hours of driving
    rest_interval = 4 * 3600  # 4 hours in seconds
    number_of_rests = int(total_duration // rest_interval)

    for i in range(1, number_of_rests):
        # Evenly distribute rest stops along the route's coordinate list.
        index = int((i / number_of_rests) * (len(coordinates) - 1))
        rest_point = {
            "type": "rest",
            "coordinates": coordinates[index],
            "description": f"Rest Stop {i}",
        }
        rests.append(rest_point)    
    
    return rests

def calculate_fueling_locations(route_data):
    """
    Calculate fueling locations along the route.
    """
    fueling_locations = []
    coordinates = route_data['routes'][0]['geometry']['coordinates']
    total_distance = route_data['routes'][0]['distance']  # Distance in meters
    
    # Add a fueling stop every 1000 miles (1609344 meters)
    fueling_interval = 1609344  # 1000 miles in meters
    number_of_fueling_stops = int(total_distance // fueling_interval)
    
    for i in range(1, number_of_fueling_stops):
        
        index = i * 100
        # If the index exceeds the available coordinates, use the last coordinate
        if index >= len(coordinates):
            index = len(coordinates) - 1
        fueling_point = {
            "type": "fueling",
            "coordinates": coordinates[index], 
            "description": f"Fueling Stop {i}",
        }
        fueling_locations.append(fueling_point)
    
    return fueling_locations

def generate_daily_logs(trip, route_data):
    MAX_DAILY_DRIVING = 11  # hours
    FUEL_STOP_INTERVAL = 1000  # miles
    AVG_SPEED = 50 
    MIN_OFF_DUTY = 10  # hours

    total_miles = route_data['distance_miles']
    total_driving_hours = total_miles / AVG_SPEED
    total_days = max(1, ceil(total_driving_hours / MAX_DAILY_DRIVING))
    current_time = timezone.now()

    # Helper function to format coordinates
    def format_coords(coords):
        return f"{coords[0]},{coords[1]}"

    # Get coordinates from route_data
    pickup_coords = format_coords(route_data['stops'][0]['coordinates'])
    dropoff_coords = format_coords(route_data['stops'][1]['coordinates'])
    
    # Get fueling and rest coordinates
    fueling_stops = [format_coords(f['coordinates']) for f in route_data.get('fuel_stops', [])]
    print("Fuel stops: ", fueling_stops)
    rest_stops = [format_coords(r['coordinates']) for r in route_data.get('rests', [])]
    
    # Interpolate coordinates for driving segments
    def get_driving_coords(progress):
        """Get coordinates string based on trip progress (0 to 1)"""
        if progress <= 0:
            return pickup_coords
        if progress >= 1:
            return dropoff_coords
        
        # Parse original coordinates
        pickup_lon, pickup_lat = map(float, pickup_coords.split(','))
        dropoff_lon, dropoff_lat = map(float, dropoff_coords.split(','))
        
        # Calculate interpolated coordinates
        lon = pickup_lon + (dropoff_lon - pickup_lon) * progress
        lat = pickup_lat + (dropoff_lat - pickup_lat) * progress
        return f"{lon},{lat}"

    # 1. Create pickup activity
    pickup_log = DailyLog.objects.create(
        trip=trip,
        date=current_time.date(),
        total_miles_driven=0,
        remarks="Pickup activity"
    )
    DutyStatus.objects.create(
        log=pickup_log,
        status='ON',
        start_time=current_time,
        end_time=current_time + timedelta(hours=1),
        distance=0,
        coordinates=pickup_coords
    )
    current_time += timedelta(hours=1)
    
    # 2. Generate driving days
    remaining_miles = total_miles
    fuel_stop_index = 0
    rest_stop_index = 0
    
    for day in range(total_days):
        miles_today = min(remaining_miles, MAX_DAILY_DRIVING * AVG_SPEED)
        hours_today = miles_today / AVG_SPEED
        remaining_miles -= miles_today
        progress = 1 - (remaining_miles / total_miles)
        
        daily_log = DailyLog.objects.create(
            trip=trip,
            date=current_time.date(),
            total_miles_driven=miles_today,
            remarks=f"Day {day+1} of driving"
        )
        
        # Driving segment coordinates (midpoint of this day's journey)
        mid_progress = progress - (miles_today/total_miles/2)
        driving_coords = get_driving_coords(mid_progress)
        
        DutyStatus.objects.create(
            log=daily_log,
            status='D',
            start_time=current_time,
            end_time=current_time + timedelta(hours=hours_today),
            distance=miles_today,
            coordinates=driving_coords
        )
        current_time += timedelta(hours=hours_today)
        
        # Add fuel stops if needed
        cumulative_miles = total_miles - remaining_miles
        if (fuel_stop_index < len(fueling_stops)) and \
           (cumulative_miles >= (fuel_stop_index + 1) * FUEL_STOP_INTERVAL):
            
            DutyStatus.objects.create(
                log=daily_log,
                status='F',
                start_time=current_time,
                end_time=current_time + timedelta(minutes=30),
                distance=0,
                coordinates=fueling_stops[fuel_stop_index]
            )
            current_time += timedelta(minutes=30)
            fuel_stop_index += 1
        
        
        # Add rest stops
        if rest_stop_index < len(rest_stops):
            DutyStatus.objects.create(
                log=daily_log,
                status='OFF',
                start_time=current_time,
                end_time=current_time + timedelta(hours=MIN_OFF_DUTY),
                distance=0,
                coordinates=rest_stops[rest_stop_index]
            )
            current_time += timedelta(hours=MIN_OFF_DUTY)
            rest_stop_index += 1
    
    # 3. Create dropoff activity
    dropoff_log = DailyLog.objects.create(
        trip=trip,
        date=current_time.date(),
        total_miles_driven=0,
        remarks="Dropoff activity"
    )
    DutyStatus.objects.create(
        log=dropoff_log,
        status='ON',
        start_time=current_time,
        end_time=current_time + timedelta(hours=1),
        distance=0,
        coordinates=dropoff_coords
    )
    