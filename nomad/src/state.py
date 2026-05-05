from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4
import json
import os

from pydantic import BaseModel, Field, model_validator


class TravelNeeds(BaseModel):
    """What components the user explicitly needs. Default = False (not needed unless stated)."""
    flight: bool = Field(False, description="User explicitly needs flight booking")
    hotel: bool = Field(False, description="User explicitly needs hotel booking")
    activity: bool = Field(False, description="User explicitly needs activity/restaurant/attraction search")


class TravelConstraints(BaseModel):
    """The explicit Constraint Layer decoupled from tool execution."""

    origin: Optional[str] = Field(None, description="Starting location/airport")
    destination: Optional[str] = Field(None, description="Target destination")
    start_date: Optional[str] = Field(None, description="Departure date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Return date (YYYY-MM-DD)")
    duration_days: Optional[int] = Field(None, description="Trip length in days (used to compute end_date if missing)")
    budget_usd: Optional[float] = Field(None, description="Maximum total budget in USD")
    hotel_budget_per_night: Optional[float] = Field(None, description="Maximum hotel cost per night in USD")
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
    hotel_location: Optional[str] = Field(
        None, description="Specific hotel neighborhood or area, e.g. 'near Westminster', 'downtown'"
    )

    @model_validator(mode="after")
    def _compute_end_date(self):
        """Auto-fill end_date from start_date + duration_days when end_date is missing."""
        if self.start_date and self.duration_days and not self.end_date:
            from datetime import timedelta
            try:
                start = datetime.strptime(self.start_date, "%Y-%m-%d")
                end = start + timedelta(days=self.duration_days)
                self.end_date = end.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return self

    def is_ready_for_flight(self) -> bool:
        """Check if we have enough info to search flights"""
        return all([self.origin, self.destination, self.start_date, self.end_date])

    def is_ready_for_hotel(self) -> bool:
        """Check if we have enough info to search hotels"""
        return all([self.destination, self.start_date, self.end_date])

    def is_ready_for_logistics(self) -> bool:
        """Backward compat: check if we have enough info for both flights and hotels"""
        return self.is_ready_for_flight()


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

    task_id: Optional[str] = Field(None, description="Unique task identifier for plan tracking. Auto-generated if not provided.")
    constraints: TravelConstraints = Field(default_factory=TravelConstraints)
    needs: TravelNeeds = Field(default_factory=TravelNeeds)
    draft_itinerary: Optional[Itinerary] = None
    delegation_plan: Optional[str] = None  # "logistics", "activities", "both", "none"
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    last_verification: Optional[Dict[str, Any]] = Field(None, description="Results of the last verification step")
    @model_validator(mode='after')
    def generate_task_id_if_missing(self):
        """Auto-generate task_id if not provided"""
        if not self.task_id:
            # Format: plan_20260325_143022_a1b2c3
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_suffix = str(uuid4())[:6]
            self.task_id = f"plan_{timestamp}_{unique_suffix}"
        return self

    def get_context_string(self) -> str:
        """Formats the current state for the LLM prompt"""
        return f"""
CURRENT CONSTRAINTS:
{self.constraints.model_dump_json(indent=2)}

CURRENT ITINERARY:
{self.draft_itinerary.model_dump_json(indent=2) if self.draft_itinerary else "None"}
"""

    def save_session(self, directory: str = None) -> str:
        """Save the current state to a JSON file for later restoration.
        Returns the file path."""
        from config import OUTPUT_DIR
        session_dir = os.path.join(directory or OUTPUT_DIR, "sessions")
        os.makedirs(session_dir, exist_ok=True)
        path = os.path.join(session_dir, f"{self.task_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
        return path

    @classmethod
    def load_session(cls, task_id: str, directory: str = None) -> "TravelState":
        """Restore a previously saved session by task_id."""
        from config import OUTPUT_DIR
        session_dir = os.path.join(directory or OUTPUT_DIR, "sessions")
        path = os.path.join(session_dir, f"{task_id}.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    @staticmethod
    def list_sessions(directory: str = None) -> List[str]:
        """List all saved session task_ids."""
        from config import OUTPUT_DIR
        session_dir = os.path.join(directory or OUTPUT_DIR, "sessions")
        if not os.path.isdir(session_dir):
            return []
        return [f.replace(".json", "") for f in os.listdir(session_dir) if f.endswith(".json")]
