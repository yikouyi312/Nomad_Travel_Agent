import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY environment variable is missing.")

SERP_API_KEY = os.getenv("SERP_API")
if not SERP_API_KEY:
    raise ValueError("SERP_API environment variable is missing.")

# Constants
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096
MAX_AGENT_TURNS = 5

# Unified output directory - all artifacts stored here
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CACHE_DIR = os.path.join(OUTPUT_DIR, "cache")
VERIFICATION_DIR = os.path.join(OUTPUT_DIR, "verification_results")
CANDIDATES_DIR = os.path.join(OUTPUT_DIR, "search_candidates")
PLANS_DIR = os.path.join(OUTPUT_DIR, "plans")
EVALUATIONS_DIR = os.path.join(OUTPUT_DIR, "evaluations")

for _d in [CACHE_DIR, VERIFICATION_DIR, CANDIDATES_DIR, PLANS_DIR, EVALUATIONS_DIR]:
    os.makedirs(_d, exist_ok=True)
