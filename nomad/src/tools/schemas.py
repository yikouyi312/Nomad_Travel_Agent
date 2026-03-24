FLIGHT_SEARCH_SCHEMA = {
    "name": "search_flights",
    "description": "Search for round-trip flights using Google Flights. You must provide origin, destination, departure date, and return date.",
    "input_schema": {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "The IATA airport code for the origin (e.g., 'JFK', 'SFO', 'LHR').",
            },
            "destination": {
                "type": "string",
                "description": "The IATA airport code for the destination (e.g., 'JFK', 'SFO', 'LHR').",
            },
            "departure_date": {
                "type": "string",
                "description": "The outbound departure date in YYYY-MM-DD format.",
            },
            "return_date": {
                "type": "string",
                "description": "The return flight date in YYYY-MM-DD format.",
            },
        },
        "required": ["origin", "destination", "departure_date", "return_date"],
    },
}

HOTEL_SEARCH_SCHEMA = {
    "name": "search_hotels",
    "description": "Search for hotels in a specific location for given dates.",
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city or neighborhood to search in (e.g., 'Manhattan, New York' or 'Tokyo, Japan').",
            },
            "check_in": {
                "type": "string",
                "description": "Check-in date in YYYY-MM-DD format.",
            },
            "check_out": {
                "type": "string",
                "description": "Check-out date in YYYY-MM-DD format.",
            },
            "adults": {
                "type": "integer",
                "description": "Number of adults staying in the room.",
            },
        },
        "required": ["location", "check_in", "check_out"],
    },
}

PLACE_SEARCH_SCHEMA = {
    "name": "search_places",
    "description": "Search for specific places, restaurants, landmarks, or activities in a location (e.g., 'vegetarian restaurants', 'museums', 'Central Park').",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What you are searching for (e.g., 'fine dining', 'Eiffel Tower', 'hiking trails').",
            },
            "location": {
                "type": "string",
                "description": "The city or neighborhood to center the search around.",
            },
        },
        "required": ["query", "location"],
    },
}

LOGISTICS_TOOLS = [FLIGHT_SEARCH_SCHEMA, HOTEL_SEARCH_SCHEMA]
ACTIVITIES_TOOLS = [PLACE_SEARCH_SCHEMA]
ALL_TOOLS = [FLIGHT_SEARCH_SCHEMA, HOTEL_SEARCH_SCHEMA, PLACE_SEARCH_SCHEMA]
