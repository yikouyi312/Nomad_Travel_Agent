from typing import Any, Dict

import requests
from cache import cached_api_call
from config import SERP_API_KEY

SERP_API_URL = "https://serpapi.com/search"


@cached_api_call
def search_flights(
    origin: str, destination: str, departure_date: str, return_date: str
) -> Dict[str, Any]:
    """
    Search for flights using Google Flights API.
    Dates must be YYYY-MM-DD.
    """
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "return_date": return_date,
        "currency": "USD",
        "hl": "en",
        "api_key": SERP_API_KEY,
    }

    response = requests.get(SERP_API_URL, params=params)
    response.raise_for_status()
    data = response.json()

    # Extract just the best flights to keep context window small
    best_flights = data.get("best_flights", [])[:3]
    other_flights = data.get("other_flights", [])[:2]

    return {"best_flights": best_flights, "other_flights": other_flights}


@cached_api_call
def search_hotels(
    location: str, check_in: str, check_out: str, adults: int = 1
) -> Dict[str, Any]:
    """
    Search for hotels using Google Hotels API.
    Dates must be YYYY-MM-DD.
    """
    params = {
        "engine": "google_hotels",
        "q": location,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "adults": adults,
        "currency": "USD",
        "hl": "en",
        "api_key": SERP_API_KEY,
    }

    response = requests.get(SERP_API_URL, params=params)
    response.raise_for_status()
    data = response.json()

    # Extract top 5 properties
    properties = data.get("properties", [])[:5]

    return {"properties": properties}


@cached_api_call
def search_places(query: str, location: str) -> Dict[str, Any]:
    """
    Search for local places (restaurants, landmarks, activities) using Google Maps/Local.
    """
    params = {
        "engine": "google_local",
        "q": query,
        "location": location,
        "hl": "en",
        "gl": "us",
        "api_key": SERP_API_KEY,
    }

    response = requests.get(SERP_API_URL, params=params)
    response.raise_for_status()
    data = response.json()

    # Extract top 5 local results
    results = data.get("local_results", [])[:5]

    return {"local_results": results}
