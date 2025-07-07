# Developer & API Reference

This file is the **single source of truth** once code and data start to drift.  
Keep it updated!

---

## 1. API Endpoints

### NFL.com (unofficial v2 - Optimized)

| Purpose | Template URL | Notes |
|---------|--------------|-------|
| Team home page (weekly stats) | `https://fantasy.nfl.com/league/{leagueId}/history/{season}/teamhome?statCategory=stats&statSeason={season}&statType=weekStats&statWeek={week}&teamId={teamId}&week={week}` | **Optimized scraper with 0.5s wait times** |
| League standings | `https://fantasy.nfl.com/league/{leagueId}/history/{season}/standings` | Used for team discovery |
| Scoreboard (schedule + lineups) | `https://api.fantasy.nfl.com/v1/league/{leagueId}/scoreboard?week={w}&format=json` | Seasons ≤ 2024 (legacy) |
| Player season/week stats | `https://api.fantasy.nfl.com/v1/players/stats?statType=weekStats&season={yr}&week={w}&format=json` | No auth required (legacy) |

### Sleeper

| Purpose | Template URL |
|---------|--------------|
| League metadata | `https://api.sleeper.app/v1/league/{leagueId}` |
| All NFL players (ID map) | `https://api.sleeper.app/v1/players/nfl` |
| Draft board | `https://api.sleeper.app/v1/draft/{draftId}/picks` |

---

## 2. NFL Scraper Performance

### Optimized v2 Scraper (Current)
- **Concurrent scraping**: ~6.4s for 12 teams
- **Sequential scraping**: ~8.8s for 12 teams  
- **Wait times**: 0.5s (optimized for speed + reliability)
- **Features**: Driver reuse, team ID caching, concurrent execution
- **Data extraction**: 146+ players per week with full stats

### Performance Comparison
| Method | Time (12 teams) | Speed vs Original |
|--------|----------------|-------------------|
| Concurrent (v2) | 6.36s | 5.8x faster |
| Sequential (v2) | 8.76s | 1.4x faster |
| Original (v1) | 12.67s | baseline |

---

## 3. Local SQLite Schema (DDL)

```sql
CREATE TABLE dim_player (
  player_id         TEXT PRIMARY KEY,
  full_name         TEXT,
  position          TEXT,
  nfl_player_id     TEXT,
  sleeper_player_id TEXT,
  first_year        INTEGER
);

CREATE TABLE fact_player_week (
  player_id       TEXT REFERENCES dim_player(player_id),
  season          INTEGER,
  week            INTEGER,
  team_id         INTEGER,
  lineup_slot     TEXT,
  fantasy_points  FLOAT,
  raw_stats       JSON,
  PRIMARY KEY (player_id, season, week)
);

-- Other tables (dim_team, fact_team_week, fact_draft_pick, dim_league_season)
-- are defined in src/transform/build_star_schema.py and kept in sync here.
```

---

## 4. CLI Usage

```bash
# Ingest everything for the 2012 season from NFL.com (optimized v2)
python -m src.cli ingest --provider nfl --season 2012

# Test the optimized scraper performance
python src/ingest/nfl/test_scraper.py

# Re-build star schema after new raw drops
python -m src.cli transform build_star

# Flags
#   --dry-run   → Parse + log, but write nothing
#   --force     → Ignore cache and download fresh
```

---

## 5. Environment Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pre-commit install          # black + ruff hooks
pytest                      # run unit tests
```

---

## 6. Caching & Rate Limits

* Cached responses live in `data/cache/{sha256(url)}.json`.  
* Default TTL is **14 days**; override with `--refresh`.  
* Courtesy limits: **NFL** < 30 req/min • **Sleeper** ~1 req/sec (no official cap).  
* **Team ID caching**: Rediscovered team IDs cached to avoid repeated lookups

---

## 7. Known Quirks

| Issue | Work-around |
|-------|-------------|
| NFL player IDs reset in 2013 data dump | Match on `(full_name, position)` first, then bridge to Sleeper IDs. |
| Auction drafts (2021 +) return `round = 0` | Detect `draft_type == "auction"` and rely on the `price` field. |
| Dynamic JS content on NFL pages | 0.5s wait times + explicit element waiting |
| Team discovery from standings page | Multiple fallback methods for finding team IDs |
