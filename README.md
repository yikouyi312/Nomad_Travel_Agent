# Nomad Travel Agent

An AI-powered travel planning agent that helps you plan trips with flights, hotels, restaurants, and activities.

## Features

- **Multi-agent architecture**: Orchestrator, Specialists (Logistics & Activities), and Verifier
- **Real-time search**: Flights, hotels, restaurants, and attractions via SerpAPI
- **Constraint-aware planning**: Respects your budget, dates, and preferences
- **Verification layer**: Ensures itineraries meet all specified constraints

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API Keys:
  - [Anthropic API Key](https://console.anthropic.com/)
  - [SerpAPI Key](https://serpapi.com/)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/CS498_Nomad_Traveller_Agent.git
   cd CS498_Nomad_Traveller_Agent
   ```

2. **Create a `.env` file** in the repository root:
   ```bash
   CLAUDE_API_KEY=your-anthropic-api-key
   SERP_API=your-serpapi-key
   ```

3. **Install dependencies**
   ```bash
   uv pip install -r requirements.txt
   ```

## Running the Agent

### Using uv (recommended)

```bash
cd nomad && uv run --with-requirements ../requirements.txt python -m src.main
```

### Using pip/venv

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the agent
cd nomad && python -m src.main
```

## Usage

Once running, you'll see an interactive prompt:

```
Welcome to Nomad Travel Agent!
Type 'quit' or 'exit' to stop.
-----------------------------------

You:
```

Enter your travel request with details like:
- Origin and destination cities
- Travel dates
- Budget
- Number of travelers
- Any preferences (e.g., dietary restrictions, interests)

**Example:**
```
You: I want to plan a trip from San Francisco to Tokyo for 5 days from April 10 to April 15, 2026 with a budget of $3000
```

The agent will:
1. Analyze your request and extract constraints
2. Search for flights and hotels (Logistics Specialist)
3. Find restaurants and activities (Activities Specialist)
4. Verify the itinerary meets all constraints
5. Present a formatted travel plan

## Project Structure

```
.
├── nomad/
│   ├── src/
│   │   ├── agents/
│   │   │   ├── orchestrator.py   # Intent classification & delegation
│   │   │   ├── specialist.py     # Logistics & Activities specialists
│   │   │   └── verifier.py       # Constraint verification
│   │   ├── tools/
│   │   │   ├── dispatch.py       # Tool execution
│   │   │   ├── schemas.py        # Tool definitions
│   │   │   └── serpapi.py        # SerpAPI integration
│   │   ├── cache.py              # API response caching
│   │   ├── config.py             # Configuration & env vars
│   │   ├── llm.py                # Claude API client
│   │   ├── main.py               # Entry point
│   │   └── state.py              # Travel state management
│   └── .env                      # (create this)
├── nomad_benchmark/              # Evaluation framework
├── requirements.txt
└── README.md
```

## License

MIT
