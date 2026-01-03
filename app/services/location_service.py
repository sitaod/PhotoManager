import os
import requests
from typing import Optional, Tuple, Dict, Any

def _convert_to_degrees(value: Tuple[Any, Any, Any]) -> float:
    """
    Helper function to convert the GPS coordinates stored in the EXIF to degress in float format
    :param value: tuple of (degrees, minutes, seconds)
    :return: float value of degrees
    """
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)

def get_gps_details(exif_dict: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """
    Extracts GPS Lat and Lon from EXIF data
    :param exif_dict: Dictionary of EXIF data
    :return: Tuple (lat, lon) or None
    """
    if 'GPSInfo' not in exif_dict:
        return None

    gps_info = exif_dict['GPSInfo']
    
    # Check if required keys exist
    # 1: GPSLatitudeRef, 2: GPSLatitude, 3: GPSLongitudeRef, 4: GPSLongitude
    if not all(k in gps_info for k in [1, 2, 3, 4]):
        return None

    try:
        lat_ref = gps_info[1]
        lat_coords = gps_info[2]
        lon_ref = gps_info[3]
        lon_coords = gps_info[4]

        lat = _convert_to_degrees(lat_coords)
        lon = _convert_to_degrees(lon_coords)

        if lat_ref != 'N':
            lat = -lat
        if lon_ref != 'E':
            lon = -lon

        return lat, lon
    except Exception:
        return None

def get_city_from_coords(lat: float, lon: float) -> Optional[str]:
    """
    Uses Amap API to get city name from coordinates (Reverse Geocoding)
    :param lat: Latitude
    :param lon: Longitude
    :return: City name or None
    """
    api_key = os.environ.get('AMAP_KEY')
    if not api_key:
        return None

    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": api_key,
        "location": f"{lon},{lat}", # Amap expects lon,lat
        "output": "json",
        "radius": 1000,
        "extensions": "base"
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '1' and 'regeocode' in data:
                address_component = data['regeocode'].get('addressComponent', {})
                
                # Try to get city
                city = address_component.get('city')
                
                # If city is empty or list (sometimes happens for direct-controlled municipalities like Beijing), use province
                if not city or isinstance(city, list):
                    city = address_component.get('province')
                
                # If still empty, try district
                if not city or isinstance(city, list):
                    city = address_component.get('district')
                    
                if isinstance(city, str) and city:
                    return city
    except Exception as e:
        print(f"Amap API Error: {e}")
        pass

    return None
