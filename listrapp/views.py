import certifi
import json
import re
import ssl
import numpy as np
import plotly.express as px # type: ignore

# from apify_client import ApifyClient
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from pathlib import Path

def index(request):
    return render(request, "listrapp/template.html")

# # Define the JSON file path for storing data
JSON_FILE_PATH = Path("airbnb_data.json")

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def get_lat_long(street_address):
    """
    Gets the latitude and longitude for a given street address in Austin, TX.
    
    Args:
        street_address (str): The street number and name (e.g., "2005 Antone Street").
        
    Returns:
        tuple: A tuple containing (latitude, longitude) or None if not found.
    """
    # Append "Austin, TX" to the street address
    full_address = f"{street_address}, Austin, TX"
    
    # Create an SSL context that ignores certificate verification (for development/testing only)
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # Use geopy to perform the geocoding
    geolocator = Nominatim(user_agent="geopy_example", timeout=10, ssl_context=ctx)
    location = geolocator.geocode(full_address)
    
    if location:
        latitude, longitude = location.latitude, location.longitude
        return latitude, longitude
    else:
        return None


def search_proximity(request):
    try:
        # Define Austin, TX center coordinates
        latitude, longitude = 30.2672, -97.7431  # Fixed central point

        # Load Permitted Properties data
        with open("permitted_properties.json", "r") as permitted_file:
            permitted_properties = json.load(permitted_file)

        # Load Airbnb data
        with open("airbnb_listings.json", "r") as airbnb_file:
            airbnb_data = json.load(airbnb_file)

        # Get radius and data type from request
        data = json.loads(request.body)
        radius_km = max(1, min(float(data.get("radius", 20)), 30))
        data_type = data.get("data_type", "both")  # Can be "permitted", "airbnb", or "both"

        permitted_matches = []
        airbnb_matches = []

        # Check for properties within radius
        for item in permitted_properties:
            try:
                prop_lat = item.get("latitude")
                prop_lon = item.get("longitude")

                if prop_lat is not None and prop_lon is not None:
                    prop_lat, prop_lon = float(prop_lat), float(prop_lon)
                    distance = geodesic((prop_lat, prop_lon), (latitude, longitude)).kilometers

                    if distance <= radius_km:
                        permitted_matches.append({
                            "address": item.get("full_address", "N/A"),
                            "latitude": prop_lat,
                            "longitude": prop_lon,
                            "distance": round(distance, 2)
                        })
            except (KeyError, ValueError, TypeError) as e:
                print(f"⚠️ Skipping invalid entry in permited_properties: {item} → Error: {e}")

        for item in airbnb_data:
            try:
                prop_lat = item.get("latitude")
                prop_lon = item.get("longitude")

                if prop_lat is not None and prop_lon is not None:
                    prop_lat, prop_lon = float(prop_lat), float(prop_lon)
                    distance = geodesic((prop_lat, prop_lon), (latitude, longitude)).kilometers

                    if distance <= radius_km:
                        airbnb_matches.append({
                            "address": item.get("address", "N/A"),
                            "latitude": prop_lat,
                            "longitude": prop_lon,
                            "distance": round(distance, 2)
                        })
            except (KeyError, ValueError, TypeError) as e:
                print(f"⚠️ Skipping invalid entry in airbnb_data: {item} → Error: {e}")

        # rework this
        if radius_km <= 2:
            zoom_level = 14
        elif radius_km <= 5:
            zoom_level = 12
        elif radius_km <= 10:
            zoom_level = 11
        elif radius_km <= 20:
            zoom_level = 10
        elif radius_km <= 40:
            zoom_level = 9.75
        else:
            zoom_level = 6

        fig = px.scatter_mapbox(
            [], lat=[], lon=[], text=[], zoom=zoom_level, center={"lat": latitude, "lon": longitude},
            title="Austin, TX - Airbnb (Red) vs Permitted (Blue)"
        )

        if data_type in ["both", "airbnb"]:
            airbnb_layer = px.scatter_mapbox(
                airbnb_matches, lat="latitude", lon="longitude", text="address",
                color_discrete_sequence=["red"],
                opacity=0.5
            )
            for trace in airbnb_layer.data:
                fig.add_trace(trace)

        if data_type in ["both", "permitted"]:
            permitted_layer = px.scatter_mapbox(
                permitted_matches, lat="latitude", lon="longitude", text="address",
                color_discrete_sequence=["blue"],
                opacity=0.5
            )
            for trace in permitted_layer.data:
                fig.add_trace(trace)    

        # Generate circle points for the radius ring
        num_points = 100
        angles = np.linspace(0, 2 * np.pi, num_points)
        circle_lats = latitude + (radius_km / 111) * np.sin(angles)
        circle_lons = longitude + (radius_km / (111 * np.cos(np.radians(latitude)))) * np.cos(angles)

        fig.add_trace(px.line_mapbox(lat=circle_lats, lon=circle_lons).data[0])
        fig.data[-1].update(line=dict(color="grey", width=2))

        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 50, "l": 0, "b": 0})

        return JsonResponse({"status": "success", "plot": fig.to_json()})

    except Exception as e:
        print(f"❌ Error in search_proximity: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)



""" FEATURE TO BE ADDED LATER """

# def normalize_address(address):
#     """Normalize an address by removing commas and converting it to lowercase."""
#     return re.sub(r"[,]", "", address).lower()

# def search_addresses(request):
#     try:
#         if request.method == "POST":
#             # Parse the list of addresses from the request
#             body = json.loads(request.body)
#             addresses_to_search = body.get("addresses", [])

#             if not addresses_to_search:
#                 return JsonResponse({"status": "error", "message": "No addresses provided."}, status=400)

#             # Load Airbnb data
#             with open("airbnb_data.json", "r") as airbnb_file:
#                 airbnb_data = json.load(airbnb_file)  # airbnb_data is likely a list of dictionaries

#             # Normalize search addresses
#             normalized_search_addresses = [normalize_address(addr) for addr in addresses_to_search]

#             # Check for matches
#             matches = []
#             for entry in airbnb_data:  # Iterate directly over the list
#                 if "address" in entry:
#                     normalized_entry_address = normalize_address(entry["address"])
#                     for search_address in normalized_search_addresses:
#                         if search_address in normalized_entry_address:
#                             matches.append({
#                                 "address": entry["address"],
#                                 "url": entry.get("url", "#"),  # Handle missing keys safely
#                                 "source": "Airbnb"
#                             })

#             # Return matches
#             if matches:
#                 return JsonResponse({"status": "success", "matches": matches}, safe=False)
#             else:
#                 return JsonResponse({"status": "success", "message": "No matches found."})

#         return JsonResponse({"status": "error", "message": "Invalid request method."}, status=405)

#     except Exception as e:
#         return JsonResponse({"status": "error", "message": str(e)}, status=500)
