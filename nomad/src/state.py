from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TravelConstraints(BaseModel):
    """The explicit Constraint Layer decoupled from tool execution."""

    origin: Optional[str] = Field(None, description="Starting location/airport")
    destination: Optional[str] = Field(None, description="Target destination")
    start_date: Optional[str] = Field(None, description="Departure date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Return date (YYYY-MM-DD)")
    budget_usd: Optional[float] = Field(None, description="Maximum total budget in USD")
    num_travelers: int = Field(1, description="Number of adults traveling")

    # Soft constraints / Preferences
    dietary_needs: List[str] = Field(
        default_factory=list, description="E.g., 'vegetarian', 'vegan', 'halal'"
    )
    interests: List[str] = Field(
        default_factory=list, description="E.g., 'museums', 'hiking', 'fine dining'"
    )
    preferred_hotel_rating: Optional[int] = Field(
        None, description="Minimum hotel star rating (1-5)"
    )

    def is_ready_for_logistics(self) -> bool:
        """Check if we have enough info to book flights/hotels"""
        return all([self.origin, self.destination, self.start_date, self.end_date])


class Flight(BaseModel):
    airline: str
    flight_number: str
    departure_time: str
    arrival_time: str
    price: float


class Hotel(BaseModel):
    name: str
    location: str
    check_in: str
    check_out: str
    price_per_night: float
    total_price: float


class Activity(BaseModel):
    name: str
    type: str
    location: str
    estimated_cost: float
    datetime: Optional[str] = None


class DayPlan(BaseModel):
    date: str
    activities: List[Activity] = Field(default_factory=list)


class Itinerary(BaseModel):
    flights: List[Flight] = Field(default_factory=list)
    hotels: List[Hotel] = Field(default_factory=list)
    days: List[DayPlan] = Field(default_factory=list)
    total_estimated_cost: float = 0.0


class TravelState(BaseModel):
    """The complete multi-turn state object"""

    constraints: TravelConstraints = Field(default_factory=TravelConstraints)
    draft_itinerary: Optional[Itinerary] = None
    delegation_plan: Optional[str] = None  # "logistics", "activities", "both", "none"
    messages: List[Dict[str, Any]] = Field(default_factory=list)

    def get_context_string(self) -> str:
        """Formats the current state for the LLM prompt"""
        return f"""
CURRENT CONSTRAINTS:
{self.constraints.model_dump_json(indent=2)}

CURRENT ITINERARY:
{self.draft_itinerary.model_dump_json(indent=2) if self.draft_itinerary else "None"}
"""
