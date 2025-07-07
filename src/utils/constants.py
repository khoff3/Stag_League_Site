"""
Constants and configuration for the Stag League History project.
"""

from enum import Enum
from typing import Dict, List, NamedTuple
from datetime import datetime

class Phase(NamedTuple):
    """Represents a project phase with its metadata."""
    name: str
    target_date: datetime
    deliverables: List[str]
    status: str = "⬜"  # Default status is not started

class ProjectPhases(Enum):
    """Enumeration of all project phases with their metadata."""
    BOOTSTRAP = Phase(
        name="Bootstrap",
        target_date=datetime(2025, 6, 5),
        deliverables=[
            "Repo skeleton",
            "venv/poetry setup",
            "black + ruff configuration",
            "pre-commit hooks",
            "CI smoke test"
        ]
    )
    
    NFL_INGEST = Phase(
        name="NFL Ingest",
        target_date=datetime(2025, 6, 12),
        deliverables=[
            "schedule.py implementation",
            "team_weeks.py implementation",
            "player_weeks.py implementation",
            "2011-12 data caching"
        ]
    )
    
    SLEEPER_INGEST = Phase(
        name="Sleeper Ingest",
        target_date=datetime(2025, 6, 12),
        deliverables=[
            "League data pulls (2021-24)",
            "Player data pulls",
            "Draft boards caching"
        ]
    )
    
    STAR_SCHEMA = Phase(
        name="Star Schema Transform",
        target_date=datetime(2025, 6, 19),
        deliverables=[
            "build_star_schema.py implementation",
            "fantasy.db population",
            "SQL validation tests"
        ]
    )
    
    DRAFT_AUCTION = Phase(
        name="Draft/Auction Nuance",
        target_date=datetime(2025, 6, 26),
        deliverables=[
            "fact_draft_pick table implementation",
            "Price handling logic",
            "Snake vs auction logic",
            "Demo JOIN query"
        ]
    )
    
    FRONTEND_MVP = Phase(
        name="Front-End MVP",
        target_date=datetime(2025, 7, 10),
        deliverables=[
            "Basic Flask/Next routes",
            "League season selector",
            "Team/week view"
        ]
    )
    
    STRETCH = Phase(
        name="Stretch Goals",
        target_date=datetime(2025, 8, 1),  # Placeholder date
        deliverables=[
            "Consolation-bracket ingest",
            "GitHub Actions setup",
            "Deploy to Render/Vercel"
        ]
    )

# Directory structure constants
DIRECTORIES = {
    "DATA": {
        "RAW": "data/raw",
        "PROCESSED": "data/processed"
    },
    "SRC": {
        "INGEST": {
            "NFL": "src/ingest/nfl",
            "SLEEPER": "src/ingest/sleeper"
        },
        "TRANSFORM": "src/transform",
        "UTILS": "src/utils"
    },
    "TESTS": {
        "FIXTURES": "tests/fixtures"
    },
    "DOCS": "docs",
    "NOTEBOOKS": "notebooks"
}

# Risk levels for tracking project risks
class RiskLevel(Enum):
    HIGH = "🟥"
    MEDIUM = "🟧"
    LOW = "🟨"

# Project risks and mitigations
PROJECT_RISKS = {
    "NFL_ENDPOINT_CHANGES": {
        "description": "NFL unofficial endpoints change or disappear",
        "level": RiskLevel.HIGH,
        "mitigation": "Cache all seasons early; fall back to HTML scrape in worst case"
    },
    "PLAYER_ID_MISMATCHES": {
        "description": "Player-ID mismatches between sites",
        "level": RiskLevel.MEDIUM,
        "mitigation": "Maintain bridge_player_ids.csv; manual overrides allowed"
    },
    "AUCTION_LOGIC_EDGECASES": {
        "description": "Auction logic edge-cases",
        "level": RiskLevel.LOW,
        "mitigation": "Write unit tests with 2021-24 drafts covering min/max price"
    }
} 