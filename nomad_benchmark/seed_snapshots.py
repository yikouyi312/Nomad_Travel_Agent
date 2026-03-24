"""
seed_snapshots.py
-----------------
Populates data/serp_snapshot.json by calling SerpAPI directly for every
tool call each benchmark task requires.

Snapshot structure: { task_id: { turn_N: { engine: [ result, ... ] } } }
- Tier 1 & 2: always turn_1
- Tier 3: split by turn — each turn captures what the agent would search
  for at that point in the conversation

Run from the nomad_benchmark/ directory:
    python3 seed_snapshots.py

Requires SERPAPI_KEY in .env (or environment).
"""

import os

from dotenv import load_dotenv
from src.mock_tools import SerpManager

load_dotenv()

serp = SerpManager(
    api_key=os.getenv("SERPAPI_KEY"), cache_path="data/serp_snapshot.json"
)

# ---------------------------------------------------------------------------
# All API calls needed to cover all 20 tasks.
# Format: (task_id, turn, engine, params)
# Tier 1 & 2: turn=1
# Tier 3: turn=1 for the initial plan, turn=2 for the revised plan
# ---------------------------------------------------------------------------
CALLS = [
    # ==========================================================================
    # TIER 1 — Single-turn, single-tool
    # ==========================================================================
    (
        "T1-01",
        1,
        "google_flights",
        {
            "departure_id": "ORD",
            "arrival_id": "MIA",
            "outbound_date": "2026-04-10",
            "type": 2,
            "currency": "USD",
        },
    ),
    (
        "T1-02",
        1,
        "google_flights",
        {
            "departure_id": "BOS",
            "arrival_id": "SEA",
            "outbound_date": "2026-05-05",
            "return_date": "2026-05-12",
            "currency": "USD",
        },
    ),
    (
        "T1-03",
        1,
        "google_hotels",
        {
            "q": "hotels in downtown Chicago",
            "check_in_date": "2026-06-05",
            "check_out_date": "2026-06-07",
            "currency": "USD",
        },
    ),
    (
        "T1-04",
        1,
        "google_hotels",
        {
            "q": "pet-friendly hotels in Austin Texas",
            "check_in_date": "2026-06-01",
            "check_out_date": "2026-06-03",
            "currency": "USD",
        },
    ),
    ("T1-05", 1, "google_maps", {"q": "Art Institute of Chicago hours admission fee"}),
    (
        "T1-06",
        1,
        "google_flights",
        {
            "departure_id": "LAX",
            "arrival_id": "JFK",
            "outbound_date": "2026-07-04",
            "return_date": "2026-07-11",
            "currency": "USD",
        },
    ),
    # ==========================================================================
    # TIER 2 — Single-turn, multi-tool
    # ==========================================================================
    (
        "T2-01",
        1,
        "google_flights",
        {
            "departure_id": "DAL",
            "arrival_id": "MSY",
            "outbound_date": "2026-03-20",
            "return_date": "2026-03-23",
            "currency": "USD",
        },
    ),
    (
        "T2-01",
        1,
        "google_hotels",
        {
            "q": "hotels in New Orleans Louisiana",
            "check_in_date": "2026-03-20",
            "check_out_date": "2026-03-23",
            "currency": "USD",
        },
    ),
    ("T2-01", 1, "google_maps", {"q": "jazz clubs Bourbon Street New Orleans"}),
    (
        "T2-02",
        1,
        "google_flights",
        {
            "departure_id": "SFO",
            "arrival_id": "SEA",
            "outbound_date": "2026-04-18",
            "return_date": "2026-04-20",
            "currency": "USD",
        },
    ),
    (
        "T2-02",
        1,
        "google_hotels",
        {
            "q": "pet-friendly hotels in Seattle",
            "check_in_date": "2026-04-18",
            "check_out_date": "2026-04-20",
            "currency": "USD",
        },
    ),
    ("T2-02", 1, "google_maps", {"q": "Space Needle Seattle"}),
    (
        "T2-03",
        1,
        "google_flights",
        {
            "departure_id": "JFK",
            "arrival_id": "ORD",
            "outbound_date": "2026-09-15",
            "return_date": "2026-09-16",
            "currency": "USD",
        },
    ),
    (
        "T2-03",
        1,
        "google_hotels",
        {
            "q": "hotels near Magnificent Mile Chicago",
            "check_in_date": "2026-09-15",
            "check_out_date": "2026-09-16",
            "currency": "USD",
        },
    ),
    (
        "T2-04",
        1,
        "google_flights",
        {
            "departure_id": "BOS",
            "arrival_id": "MIA",
            "outbound_date": "2026-08-05",
            "return_date": "2026-08-10",
            "currency": "USD",
        },
    ),
    (
        "T2-04",
        1,
        "google_hotels",
        {
            "q": "hotels with pool Miami Beach",
            "check_in_date": "2026-08-05",
            "check_out_date": "2026-08-10",
            "currency": "USD",
        },
    ),
    (
        "T2-05",
        1,
        "google_flights",
        {
            "departure_id": "ORD",
            "arrival_id": "DCA",
            "outbound_date": "2026-05-10",
            "return_date": "2026-05-14",
            "currency": "USD",
        },
    ),
    (
        "T2-05",
        1,
        "google_hotels",
        {
            "q": "hotels in Washington DC",
            "check_in_date": "2026-05-10",
            "check_out_date": "2026-05-14",
            "currency": "USD",
        },
    ),
    (
        "T2-05",
        1,
        "google_maps",
        {  # [0] Smithsonian
            "q": "Smithsonian National Museum Washington DC"
        },
    ),
    (
        "T2-05",
        1,
        "google_maps",
        {  # [1] Lincoln Memorial
            "q": "Lincoln Memorial Washington DC"
        },
    ),
    (
        "T2-06",
        1,
        "google_flights",
        {
            "departure_id": "JFK",
            "arrival_id": "SFO",
            "outbound_date": "2026-06-15",
            "return_date": "2026-06-18",
            "currency": "USD",
        },
    ),
    (
        "T2-06",
        1,
        "google_hotels",
        {
            "q": "hotels in San Francisco",
            "check_in_date": "2026-06-15",
            "check_out_date": "2026-06-18",
            "currency": "USD",
        },
    ),
    (
        "T2-06",
        1,
        "google_maps",
        {  # [0] Golden Gate Park
            "q": "Golden Gate Park San Francisco"
        },
    ),
    (
        "T2-06",
        1,
        "google_maps",
        {  # [1] vegan restaurants
            "q": "vegan restaurants San Francisco"
        },
    ),
    (
        "T2-07",
        1,
        "google_flights",
        {
            "departure_id": "JFK",
            "arrival_id": "LHR",
            "outbound_date": "2026-10-05",
            "return_date": "2026-10-12",
            "currency": "USD",
        },
    ),
    (
        "T2-07",
        1,
        "google_hotels",
        {
            "q": "hotels near Westminster London",
            "check_in_date": "2026-10-05",
            "check_out_date": "2026-10-12",
            "currency": "USD",
        },
    ),
    ("T2-07", 1, "google_maps", {"q": "Westminster London attractions"}),
    (
        "T2-08",
        1,
        "google_flights",
        {
            "departure_id": "SEA",
            "arrival_id": "DEN",
            "outbound_date": "2027-01-15",
            "return_date": "2027-01-19",
            "currency": "USD",
        },
    ),
    (
        "T2-08",
        1,
        "google_hotels",
        {
            "q": "hotels near ski slopes Denver Colorado",
            "check_in_date": "2027-01-15",
            "check_out_date": "2027-01-19",
            "currency": "USD",
        },
    ),
    ("T2-08", 1, "google_maps", {"q": "ski rental near Denver Colorado"}),
    # ==========================================================================
    # TIER 3 — Multi-turn: split by turn
    # Each turn reflects what the agent would search at that point
    # ==========================================================================
    # T3-01: "Plan a 3-day NYC trip under $1,200."
    #        → "Make it 4 days and add a Broadway show."
    (
        "T3-01",
        1,
        "google_hotels",
        {
            "q": "hotels in Manhattan New York City",
            "check_in_date": "2026-04-10",
            "check_out_date": "2026-04-13",
            "currency": "USD",
        },
    ),
    (
        "T3-01",
        2,
        "google_hotels",
        {  # updated: 4-day stay
            "q": "hotels in Manhattan New York City",
            "check_in_date": "2026-04-10",
            "check_out_date": "2026-04-14",
            "currency": "USD",
        },
    ),
    ("T3-01", 2, "google_maps", {"q": "Broadway shows New York City"}),
    # T3-02: "Plan a weekend trip to Miami from Chicago, budget $900."
    #        → "Change hotel to beachfront and add snorkeling."
    (
        "T3-02",
        1,
        "google_flights",
        {
            "departure_id": "ORD",
            "arrival_id": "MIA",
            "outbound_date": "2026-04-25",
            "return_date": "2026-04-27",
            "currency": "USD",
        },
    ),
    (
        "T3-02",
        1,
        "google_hotels",
        {
            "q": "hotels in Miami Florida",
            "check_in_date": "2026-04-25",
            "check_out_date": "2026-04-27",
            "currency": "USD",
        },
    ),
    (
        "T3-02",
        2,
        "google_hotels",
        {  # updated: beachfront
            "q": "beachfront hotels in Miami Beach",
            "check_in_date": "2026-04-25",
            "check_out_date": "2026-04-27",
            "currency": "USD",
        },
    ),
    ("T3-02", 2, "google_maps", {"q": "snorkeling excursions Miami Florida"}),
    # T3-03: "Plan a 3-day trip to Portland, OR from NYC, budget $1,500."
    #        → "Travel companion is vegan. Adjust restaurant recommendations."
    (
        "T3-03",
        1,
        "google_flights",
        {
            "departure_id": "JFK",
            "arrival_id": "PDX",
            "outbound_date": "2026-05-15",
            "return_date": "2026-05-18",
            "currency": "USD",
        },
    ),
    (
        "T3-03",
        1,
        "google_hotels",
        {
            "q": "hotels in Portland Oregon",
            "check_in_date": "2026-05-15",
            "check_out_date": "2026-05-18",
            "currency": "USD",
        },
    ),
    (
        "T3-03",
        2,
        "google_maps",
        {  # new: vegan restaurants
            "q": "vegan restaurants Portland Oregon"
        },
    ),
    # T3-04: "Plan a 5-day beach vacation from Boston to Miami, budget $2,500."
    #        → "Change destination to Cancun, Mexico."
    (
        "T3-04",
        1,
        "google_flights",
        {
            "departure_id": "BOS",
            "arrival_id": "MIA",
            "outbound_date": "2026-06-20",
            "return_date": "2026-06-25",
            "currency": "USD",
        },
    ),
    (
        "T3-04",
        1,
        "google_hotels",
        {
            "q": "beach hotels in Miami Florida",
            "check_in_date": "2026-06-20",
            "check_out_date": "2026-06-25",
            "currency": "USD",
        },
    ),
    (
        "T3-04",
        2,
        "google_flights",
        {  # updated: new destination
            "departure_id": "BOS",
            "arrival_id": "CUN",
            "outbound_date": "2026-06-20",
            "return_date": "2026-06-25",
            "currency": "USD",
        },
    ),
    (
        "T3-04",
        2,
        "google_hotels",
        {  # updated: Cancun
            "q": "beach hotels in Cancun Mexico",
            "check_in_date": "2026-06-20",
            "check_out_date": "2026-06-25",
            "currency": "USD",
        },
    ),
    # T3-05: "Plan a 2-day business trip to Chicago from NYC, hotel under $200/night."
    #        → "Group of 3, need suite/adjoining rooms, add group dinner."
    (
        "T3-05",
        1,
        "google_flights",
        {
            "departure_id": "JFK",
            "arrival_id": "ORD",
            "outbound_date": "2026-03-10",
            "return_date": "2026-03-12",
            "currency": "USD",
        },
    ),
    (
        "T3-05",
        1,
        "google_hotels",
        {
            "q": "hotels in Chicago Illinois",
            "check_in_date": "2026-03-10",
            "check_out_date": "2026-03-12",
            "currency": "USD",
        },
    ),
    (
        "T3-05",
        2,
        "google_hotels",
        {  # updated: suites
            "q": "hotels with suites in Chicago",
            "check_in_date": "2026-03-10",
            "check_out_date": "2026-03-12",
            "currency": "USD",
        },
    ),
    ("T3-05", 2, "google_maps", {"q": "group dinner restaurants Chicago"}),
    # T3-06: "Plan a 4-day trip to Las Vegas from LA, budget $1,000."
    #        → "Upgrade to 5-star resort on the Strip. New budget $2,500."
    (
        "T3-06",
        1,
        "google_flights",
        {
            "departure_id": "LAX",
            "arrival_id": "LAS",
            "outbound_date": "2026-04-15",
            "return_date": "2026-04-19",
            "currency": "USD",
        },
    ),
    (
        "T3-06",
        1,
        "google_hotels",
        {
            "q": "hotels in Las Vegas Nevada",
            "check_in_date": "2026-04-15",
            "check_out_date": "2026-04-19",
            "currency": "USD",
        },
    ),
    (
        "T3-06",
        2,
        "google_hotels",
        {  # updated: 5-star Strip
            "q": "5-star resort hotels Las Vegas Strip",
            "check_in_date": "2026-04-15",
            "check_out_date": "2026-04-19",
            "currency": "USD",
        },
    ),
]


def main():
    total = len(CALLS)
    succeeded = 0
    failed = []

    print(f"Seeding snapshot with {total} API calls...\n")

    for i, (task_id, turn, engine, params) in enumerate(CALLS, 1):
        print(f"[{i}/{total}] {task_id}/turn_{turn} — {engine}")
        try:
            serp.fetch(engine, params, task_id=task_id, turn=turn, mode="record")
            succeeded += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append((task_id, turn, engine, str(e)))

    print(f"\nDone. {succeeded}/{total} calls succeeded.")
    if failed:
        print(f"\nFailed calls ({len(failed)}):")
        for task_id, turn, engine, err in failed:
            print(f"  {task_id}/turn_{turn} / {engine}: {err}")


if __name__ == "__main__":
    main()
