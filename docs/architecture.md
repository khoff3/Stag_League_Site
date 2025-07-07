# Architecture Overview

> **Purpose** Describe how raw league data flows from NFL.com & Sleeper into a
> clean, query-ready dataset, and the conventions that keep this repo tidy.

## Table of Contents
1. [System Diagram](#system-diagram)  
2. [Component Details](#component-details)  
3. [Star-Schema Data Model](#star-schema-data-model)  
4. [Coding & Dev Conventions](#coding--dev-conventions)  
5. [Performance Optimizations](#performance-optimizations)  
6. [Future-Proofing Notes](#future-proofing-notes)  

---

## System Diagram

```mermaid
flowchart TD
  subgraph Ingest
    A[nfl.api_client_v2.py] -->|optimized scraping| B[raw/nfl/]
    A2[nfl.api_client_v2_optimized.py] -->|concurrent scraping| B
    A3[nfl.schedule.py] -->|weekly JSON| B
    A4[nfl.team_weeks.py] --> B
    A5[nfl.player_weeks.py] --> B
    S1[sleeper.league.py] --> B
    S2[sleeper.players.py] --> B
  end

  B --> T[transform/build_star_schema.py]
  T --> P[data/processed/ (SQLite + Parquet)]
  P --> FE[front-end API & visualizations]
```

---

## Component Details

| Layer         | Module(s)                                                     | Responsibilities                                           |
|---------------|---------------------------------------------------------------|------------------------------------------------------------|
| **Ingest**    | `src/ingest/nfl/api_client_v2.py`<br>`src/ingest/nfl/api_client_v2_optimized.py`<br>`src/ingest/nfl/*.py`<br>`src/ingest/sleeper/*.py` | **Optimized scraping** with 0.5s wait times, concurrent execution, driver reuse. Pull raw JSON, cache on disk, guarantee idempotence. |
| **Transform** | `src/transform/build_star_schema.py`                          | Normalize, merge player IDs, calculate team/player points. |
| **Storage**   | `data/processed/fantasy.db` (SQLite) + columnar Parquet files | Star schema; easy SQL & downstream analytics.              |
| **Serve**     | *TBD front-end* (Flask / Next.js etc.)                        | Interactive history explorer; CSV exports.                 |

---

## Performance Optimizations

### NFL Scraper v2 (Current)
- **Concurrent execution**: ThreadPoolExecutor with 3 workers
- **Driver reuse**: Single ChromeDriver instance per batch
- **Team ID caching**: Rediscovered IDs cached to avoid repeated lookups
- **Optimized wait times**: 0.5s (balanced speed + reliability)
- **Fallback mechanisms**: Multiple methods for team discovery

### Performance Metrics
| Method | Time (12 teams) | Improvement |
|--------|----------------|-------------|
| Concurrent (v2) | 6.36s | 5.8x faster |
| Sequential (v2) | 8.76s | 1.4x faster |
| Original (v1) | 12.67s | baseline |

---

## Star-Schema Data Model

```mermaid
erDiagram
  FACT_TEAM_WEEK }o--|| DIM_TEAM : "team_id"
  FACT_TEAM_WEEK }o--|| DIM_LEAGUE_SEASON : "league_season_id"
  FACT_PLAYER_WEEK }o--|| DIM_PLAYER : "player_id"
  FACT_PLAYER_WEEK }o--|| DIM_TEAM : "team_id"
  FACT_DRAFT_PICK }o--|| DIM_PLAYER : "player_id"

  DIM_TEAM {
    int team_id PK
    int league_id
    int season
    string franchise_name
  }

  FACT_TEAM_WEEK {
    int team_id FK
    int week
    int season
    float pts_for
    float pts_against
    char(1) result  -- W/L/T
  }

  FACT_PLAYER_WEEK {
    int player_id FK
    int team_id FK
    int week
    float fantasy_points
    string lineup_slot  -- STARTER/BENCH
    json raw_stats      -- passing_yds, rush_td, etc.
  }

  FACT_DRAFT_PICK {
    int league_id
    int season
    int player_id FK
    int nomination_price
    int final_price
    int pick_overall
  }
```

---

## Coding & Dev Conventions

* **Python 3.11**; format with **black**, lint with **ruff**.  
* Public functions include **type hints** and NumPy-style docstrings.  
* Secrets live only in **.env**; never commit credentials.  
* Tests under `tests/` use **pytest**; fixture JSON lives in `tests/fixtures/`.
* **Context managers** for resource management (drivers, connections)
* **Concurrent execution** with proper error handling and timeouts

---

## Future-Proofing Notes

* Swap SQLite for Postgres by changing only the SQLAlchemy URL.  
* `src/utils/cache.py` isolates disk caching—swap for S3 later if needed.  
* Retry wrapper logs endpoint failures to `logs/ingest.log`; stale cache keeps old data safe.
* **Scalable scraping**: Easy to adjust worker count and wait times for different environments
* **Modular design**: Separate optimized and standard scrapers for different use cases
