import boto3
import certifi
import json
import ssl
import numpy as np
import plotly.express as px # type: ignore

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

def index(request):
    return render(request, "listrapp/template.html")


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
        latitude, longitude = 30.2672, -97.7431  # Austin, TX center
        
        # S3 setup
        s3_client = boto3.client("s3")
        bucket_name = "nk.data.analysis"
        
        # Read JSON from S3
        permitted_properties = read_json_from_s3(s3_client, bucket_name, "short_term_rentals/permitted_properties.json") or []
        airbnb_data = read_json_from_s3(s3_client, bucket_name, "short_term_rentals/airbnb_listings.json") or []

        # Get radius and data type from request
        data = json.loads(request.body)
        radius_km = max(1, min(float(data.get("radius", 20)), 30))
        data_type = data.get("data_type", "both")

        permitted_matches, airbnb_matches = [], []

        # Process permitted properties
        for item in permitted_properties:
            try:
                prop_lat, prop_lon = float(item.get("latitude", 0)), float(item.get("longitude", 0))
                if prop_lat and prop_lon:
                    distance = geodesic((prop_lat, prop_lon), (latitude, longitude)).kilometers
                    if distance <= radius_km:
                        permitted_matches.append({
                            "address": item.get("full_address", "N/A"),
                            "latitude": prop_lat,
                            "longitude": prop_lon,
                            "distance": round(distance, 2)
                        })
            except (ValueError, TypeError) as e:
                print(f"⚠️ Skipping invalid entry in permitted_properties: {item} → {e}")

        # Process Airbnb data
        for item in airbnb_data:
            try:
                prop_lat, prop_lon = float(item.get("latitude", 0)), float(item.get("longitude", 0))
                if prop_lat and prop_lon:
                    distance = geodesic((prop_lat, prop_lon), (latitude, longitude)).kilometers
                    if distance <= radius_km:
                        airbnb_matches.append({
                            "address": item.get("address", "N/A"),
                            "latitude": prop_lat,
                            "longitude": prop_lon,
                            "distance": round(distance, 2)
                        })
            except (ValueError, TypeError) as e:
                print(f"⚠️ Skipping invalid entry in airbnb_data: {item} → {e}")

        # Create map visualization (unchanged)
        zoom_level = 14 if radius_km <= 2 else 12 if radius_km <= 5 else 11 if radius_km <= 10 else 10 if radius_km <= 20 else 9.75 if radius_km <= 40 else 6
        fig = px.scatter_mapbox([], lat=[], lon=[], text=[], zoom=zoom_level, center={"lat": latitude, "lon": longitude}, title="Austin, TX - Airbnb (Red) vs Permitted (Blue)")

        if data_type in ["both", "airbnb"]:
            airbnb_layer = px.scatter_mapbox(airbnb_matches, lat="latitude", lon="longitude", text="address", color_discrete_sequence=["red"], opacity=0.5)
            for trace in airbnb_layer.data:
                fig.add_trace(trace)

        if data_type in ["both", "permitted"]:
            permitted_layer = px.scatter_mapbox(permitted_matches, lat="latitude", lon="longitude", text="address", color_discrete_sequence=["blue"], opacity=0.5)
            for trace in permitted_layer.data:
                fig.add_trace(trace)

        fig.update_layout(mapbox_style="open-street-map", margin={"r": 0, "t": 50, "l": 0, "b": 0})

        return JsonResponse({"status": "success", "plot": fig.to_json()})

    except Exception as e:
        print(f"❌ Error in search_proximity: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


# Global cache
cached_data = {}

def read_json_from_s3(s3_client, bucket_name, key):
    """
    Fetches JSON from S3 and caches it to avoid multiple requests.

    Args:
        s3_client: Boto3 S3 client
        bucket_name (str): Name of the S3 bucket
        key (str): Path to the JSON file in S3

    Returns:
        list/dict: Cached JSON content
    """
    if key in cached_data:
        print(f"✅ Using cached data for {key}")
        return cached_data[key]

    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        json_content = response["Body"].read().decode("utf-8")
        data = json.loads(json_content)

        # Store in cache
        cached_data[key] = data
        print(f"📥 Fetched from S3 and cached: {key}")

        return data
    except Exception as e:
        print(f"❌ Error reading {key} from S3: {e}")
        return None

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
