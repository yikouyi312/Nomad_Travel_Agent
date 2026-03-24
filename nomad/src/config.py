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
