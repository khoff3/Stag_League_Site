#!/usr/bin/env python3
"""
Fetch and cache raw Sleeper data for the Stag Brotherhood (2023+).

Sleeper's API is public/unauthenticated. Everything is cached under
data/raw/sleeper/{season}/ so downstream transforms never re-hit the API:

    league.json            league settings (roster_positions, playoff config)
    users.json             owner accounts (display names, team names)
    rosters.json           roster_id -> owner_id, W-L, points for/against
    matchups/week_NN.json  one entry per roster; matchup_id pairs opponents;
                           includes starters[], players[], players_points{}
    winners_bracket.json   playoff bracket (r=round, t1/t2/w/l roster ids,
                           p=placement for finals games)
    losers_bracket.json    consolation bracket

Also caches a trimmed player-id lookup (data/metadata/sleeper_players.json)
from Sleeper's full player dump: sleeper_id -> {name, position, team}.

Run from repo root:  python src/ingest/sleeper/ingest_sleeper.py [--force]
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

BASE = "https://api.sleeper.app/v1"

# season -> league_id (chain discovered via previous_league_id)
LEAGUES = {
    "2023": "999467762558763008",
    "2024": "1124841435980390400",
    "2025": "1257058859575422976",
}

RAW = Path("data/raw/sleeper")
META = Path("data/metadata")

# Sleeper weekly-stat keys we keep (mapped to star-schema stat columns by the
# transform). The full per-week dump is ~2300 players x ~80 keys; trimming to
# these keeps the cache small.
STAT_KEYS = [
    "pass_yd", "pass_td", "pass_int",
    "rush_yd", "rush_td",
    "rec_yd", "rec_td",
    "pass_2pt", "rush_2pt", "rec_2pt", "fum_lost",
    "fgm", "fgm_0_19", "fgm_20_29", "fgm_30_39", "fgm_40_49", "fgm_50p", "xpm",
    "sack", "int", "fum_rec", "safe", "def_td", "td", "pts_allow",
]


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.load(r)


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=1)


def fetch_season(season: str, league_id: str, force: bool):
    out = RAW / season

    def cached(name, fetcher):
        p = out / name
        if p.exists() and not force:
            return json.load(open(p))
        data = fetcher()
        save(p, data)
        time.sleep(0.2)  # politeness
        return data

    league = cached("league.json", lambda: get(f"/league/{league_id}"))
    cached("users.json", lambda: get(f"/league/{league_id}/users"))
    cached("rosters.json", lambda: get(f"/league/{league_id}/rosters"))
    cached("winners_bracket.json", lambda: get(f"/league/{league_id}/winners_bracket"))
    cached("losers_bracket.json", lambda: get(f"/league/{league_id}/losers_bracket"))

    n_weeks = (league.get("settings") or {}).get("leg", 17) or 17
    for wk in range(1, n_weeks + 1):
        cached(f"matchups/week_{wk:02d}.json",
               lambda wk=wk: get(f"/league/{league_id}/matchups/{wk}"))

    # weekly NFL stat lines (trimmed to STAT_KEYS), for player_weeks detail
    def fetch_stats(wk):
        full = get(f"/stats/nfl/regular/{season}/{wk}")
        return {
            pid: {k: v for k, v in s.items() if k in STAT_KEYS and v}
            for pid, s in full.items()
            if any(s.get(k) for k in STAT_KEYS)
        }
    for wk in range(1, n_weeks + 1):
        cached(f"stats/week_{wk:02d}.json", lambda wk=wk: fetch_stats(wk))

    # transactions (trimmed) -> per-roster moves/trades counts in teams.csv
    def fetch_tx(wk):
        full = get(f"/league/{league_id}/transactions/{wk}")
        return [{k: t.get(k) for k in ("type", "status", "roster_ids")}
                for t in (full or [])]
    for wk in range(1, n_weeks + 1):
        cached(f"transactions/week_{wk:02d}.json", lambda wk=wk: fetch_tx(wk))

    print(f"  {season}: cached league/users/rosters/brackets + {n_weeks} matchup/stat/transaction weeks")


def fetch_player_lookup(force: bool):
    """Trimmed sleeper_id -> {name, position, team} lookup (full dump is ~5MB)."""
    p = META / "sleeper_players.json"
    if p.exists() and not force:
        print(f"  player lookup cached ({p})")
        return
    print("  fetching Sleeper player dump (large, one-time)...")
    dump = get("/players/nfl")
    trimmed = {
        pid: {
            "name": v.get("full_name") or f"{v.get('first_name','')} {v.get('last_name','')}".strip(),
            "position": v.get("position") or "",
            "team": v.get("team") or "",
        }
        for pid, v in dump.items()
    }
    save(p, trimmed)
    print(f"  player lookup saved: {len(trimmed)} players")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-fetch even if cached")
    args = ap.parse_args()

    for season, lid in LEAGUES.items():
        print(f"Season {season} (league {lid}):")
        fetch_season(season, lid, args.force)
    fetch_player_lookup(args.force)
    print("done")


if __name__ == "__main__":
    main()
