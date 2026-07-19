#!/usr/bin/env python3
"""
Transform cached Sleeper raw data (data/raw/sleeper/{season}/) into star-schema
rows, matching the shapes produced by export_site_data.py for the NFL.com era.

Key identity decisions:
  manager_id   via data/metadata/sleeper_manager_crosswalk.csv -> the same
               stable ids as 2011-2022, so careers span both platforms
  team_id      Sleeper roster_id (per-season scope, same as NFL team ids)
  player_id    Sleeper player id -> db_playerids.csv sleeper_id column -> same
               canonical gsis:/mfl: ids as the NFL era (cross-era careers)
  DEF ids      Sleeper uses team abbreviations ('KC'); normalized to the NFL-era
               'def:{Full Team Name}' scheme so defenses merge across eras

Sleeper-era notes:
  - matchups carry per-player fantasy points but not stat lines (yards/TDs),
    so stat columns are left blank for these seasons
  - playoff structure comes from winners_bracket/losers_bracket placement tags
    (p1 championship, p3 third place, p5 fifth; losers bracket = 7th-12th);
    there is no mediocre bowl in the Sleeper era
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

RAW = Path("data/raw/sleeper")
META = Path("data/metadata")

DEF_NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills", "CAR": "Carolina Panthers", "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos", "DET": "Detroit Lions", "GB": "Green Bay Packers",
    "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LAC": "Los Angeles Chargers", "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins", "MIN": "Minnesota Vikings",
    "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants",
    "NYJ": "New York Jets", "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}

def map_stat_line(s, is_def):
    """Sleeper weekly-stat dict -> star-schema stat columns."""
    def i(k):  # int-ish
        v = s.get(k)
        return int(v) if v else 0
    return {
        "passing_yards": i("pass_yd"),
        "passing_tds": i("pass_td"),
        # 'interceptions' means INTs thrown for offense, INTs made for DEF
        "interceptions": i("int") if is_def else i("pass_int"),
        "rushing_yards": i("rush_yd"),
        "rushing_tds": i("rush_td"),
        "receiving_yards": i("rec_yd"),
        "receiving_tds": i("rec_td"),
        "two_point_conversions": i("pass_2pt") + i("rush_2pt") + i("rec_2pt"),
        "fumbles_lost": i("fum_lost"),
        "fg_made": i("fgm"),
        "fg_0_19": i("fgm_0_19"),
        "fg_20_29": i("fgm_20_29"),
        "fg_30_39": i("fgm_30_39"),
        "fg_40_49": i("fgm_40_49"),
        "fg_50_plus": i("fgm_50p"),
        "pat_made": i("xpm"),
        "sacks": i("sack") if is_def else 0,
        "fumble_recoveries": i("fum_rec") if is_def else 0,
        "safeties": i("safe") if is_def else 0,
        "def_tds": (i("def_td") or i("td")) if is_def else 0,
        "points_allowed": i("pts_allow") if is_def else 0,
    }


PLACE_LABELS = {
    1: "Champion", 2: "Runner Up", 3: "Third Place", 4: "Fourth Place",
    5: "Fifth Place", 6: "Sixth Place", 7: "Seventh Place", 8: "Eighth Place",
    9: "Ninth Place", 10: "Tenth Place", 11: "Eleventh Place", 12: "Twelfth Place",
}


def load_crosswalk():
    xw = {}
    with open(META / "sleeper_manager_crosswalk.csv") as f:
        for r in csv.DictReader(f):
            xw[r["sleeper_user_id"]] = (r["manager_id"], r["manager_name"])
    return xw


def load_sleeper_player_map(pdb_rows):
    """sleeper_id -> canonical player_id (same ranking as the NFL-era matcher:
    prefer rows with a gsis_id, then mfl; id field order gsis/mfl/sleeper/espn)."""
    by_sleeper = defaultdict(list)
    for r in pdb_rows:
        sid = r.get("sleeper_id")
        if sid and sid != "NA":
            by_sleeper[sid].append(r)
    out = {}
    for sid, cands in by_sleeper.items():
        def rank(c):
            return (0 if c.get("gsis_id") not in (None, "", "NA") else 1,
                    0 if c.get("mfl_id") not in (None, "", "NA") else 1)
        best = sorted(cands, key=rank)[0]
        for field in ("gsis_id", "mfl_id", "sleeper_id", "espn_id"):
            v = best.get(field)
            if v not in (None, "", "NA"):
                out[sid] = f"{field.split('_')[0]}:{v}"
                break
    return out


def fpts(settings, key):
    return round((settings.get(key) or 0) + (settings.get(f"{key}_decimal") or 0) / 100.0, 2)


def build_sleeper_rows(stat_fields):
    """Returns dict of star-schema row lists for all cached Sleeper seasons."""
    xw = load_crosswalk()
    sleeper_names = json.load(open(META / "sleeper_players.json"))
    with open("db_playerids.csv") as f:
        pdb_rows = list(csv.DictReader(f))
    pid_map = load_sleeper_player_map(pdb_rows)

    manager_seasons = defaultdict(set)   # manager_id -> {season}
    manager_names = {}
    teams_rows, games_rows, standings_rows, pweeks_rows = [], [], [], []
    players_map = {}                     # player_id -> {player_id, name, position}
    unmatched = defaultdict(int)

    seasons = sorted(d.name for d in RAW.iterdir() if d.is_dir())
    for season in seasons:
        sdir = RAW / season
        league = json.load(open(sdir / "league.json"))
        users = json.load(open(sdir / "users.json"))
        rosters = json.load(open(sdir / "rosters.json"))
        wb = json.load(open(sdir / "winners_bracket.json"))
        lb = json.load(open(sdir / "losers_bracket.json"))

        settings = league.get("settings") or {}
        playoff_start = settings.get("playoff_week_start", 15)
        roster_positions = [p for p in (league.get("roster_positions") or []) if p != "BN"]

        users_by_id = {u["user_id"]: u for u in users}

        # ---- moves/trades from cached transactions ----
        moves = defaultdict(int)   # roster_id -> completed waiver/FA pickups
        trades = defaultdict(int)  # roster_id -> completed trades involved in
        tx_dir = sdir / "transactions"
        if tx_dir.exists():
            for tf in sorted(tx_dir.glob("week_*.json")):
                for t in json.load(open(tf)):
                    if t.get("status") != "complete":
                        continue
                    for rid in (t.get("roster_ids") or []):
                        if t.get("type") == "trade":
                            trades[rid] += 1
                        elif t.get("type") in ("waiver", "free_agent"):
                            moves[rid] += 1

        # ---- teams ----
        for r in rosters:
            owner = users_by_id.get(r.get("owner_id"), {})
            mid, mname = xw.get(r.get("owner_id"), (f"sleeper_{r.get('owner_id')}",
                                                    owner.get("display_name", "Unknown")))
            manager_seasons[mid].add(season)
            manager_names[mid] = mname
            team_name = (owner.get("metadata") or {}).get("team_name") or owner.get("display_name", "")
            teams_rows.append({
                "season": season,
                "team_id": str(r["roster_id"]),
                "team_name": team_name,
                "manager_id": mid,
                "moves": moves.get(r["roster_id"], 0),
                "trades": trades.get(r["roster_id"], 0),
                "waiver_priority": (r.get("settings") or {}).get("waiver_position", ""),
            })

        # ---- playoff annotation lookup: (week, frozenset{t1,t2}) -> meta ----
        playoff_meta = {}
        for bracket, is_winners in ((wb, True), (lb, False)):
            for g in bracket:
                if g.get("t1") is None or g.get("t2") is None:
                    continue
                week = playoff_start + (g.get("r", 1) - 1)
                p = g.get("p")
                if is_winners:
                    if p == 1:
                        gtype, rname = "championship", "Championship"
                    elif p == 3:
                        gtype, rname = "third_place", "Third Place"
                    elif p == 5:
                        gtype, rname = "winners", "Fifth Place"
                    else:
                        gtype, rname = "winners", f"Winners Round {g.get('r', 1)}"
                elif p == 1:
                    # the losers-bracket final crowns 7th place — the "best of
                    # the rest", i.e. the Sleeper-era Mediocre Bowl
                    gtype, rname = "mediocre_bowl", "Mediocre Bowl (7th Place)"
                else:
                    label = {3: "9th Place", 5: "Toilet Bowl"}.get(p)
                    gtype = "toilet_bowl"
                    rname = label or f"Consolation Round {g.get('r', 1)}"
                playoff_meta[(week, frozenset((str(g["t1"]), str(g["t2"]))))] = (gtype, rname)

        # ---- games + player weeks ----
        n_weeks = settings.get("leg", 17) or 17
        for wk in range(1, n_weeks + 1):
            mfile = sdir / "matchups" / f"week_{wk:02d}.json"
            if not mfile.exists():
                continue
            entries = json.load(open(mfile))
            sfile = sdir / "stats" / f"week_{wk:02d}.json"
            week_stats = json.load(open(sfile)) if sfile.exists() else {}
            by_matchup = defaultdict(list)
            for e in entries:
                if e.get("matchup_id") is not None:
                    by_matchup[e["matchup_id"]].append(e)

            for mid_, pair in sorted(by_matchup.items()):
                if len(pair) != 2:
                    continue
                a, b = sorted(pair, key=lambda e: e["roster_id"])
                key = (wk, frozenset((str(a["roster_id"]), str(b["roster_id"]))))
                gtype, rname = playoff_meta.get(key, (None, None))
                is_playoff = gtype is not None
                games_rows.append({
                    "game_id": f"{season}{wk:02d}s{mid_}",
                    "season": season,
                    "week": str(wk),
                    "home_team_id": str(a["roster_id"]),
                    "away_team_id": str(b["roster_id"]),
                    "home_points": round(a.get("points") or 0, 2),
                    "away_points": round(b.get("points") or 0, 2),
                    "is_playoff": is_playoff,
                    "game_type": gtype or "regular",
                    "round_name": rname or "",
                    "source": "scraped",  # direct API data
                })

            # player weeks (every rostered player, starters flagged with slots)
            for e in entries:
                starters = [s for s in (e.get("starters") or [])]
                ppoints = e.get("players_points") or {}
                for pid in (e.get("players") or []):
                    if not pid or pid == "0":
                        continue
                    is_starter = pid in starters
                    slot = ""
                    if is_starter:
                        idx = starters.index(pid)
                        slot = roster_positions[idx] if idx < len(roster_positions) else ""
                    else:
                        slot = "BN"
                    is_def = pid in DEF_NAMES or (pid.isalpha() and pid.isupper())
                    if is_def:
                        full = DEF_NAMES.get(pid, pid)
                        cid = f"def:{full}"
                        players_map.setdefault(cid, {"player_id": cid,
                                                     "name": f"{full} DEF",
                                                     "position": "DEF"})
                        pname, nfl_team = f"{full} DEF", pid
                    else:
                        cid = pid_map.get(pid)
                        info = sleeper_names.get(pid, {})
                        if cid is None:
                            cid = f"sleeper:{pid}"
                            unmatched[info.get("name", pid)] += 1
                        pname = info.get("name", f"player {pid}")
                        nfl_team = info.get("team", "")
                        players_map.setdefault(cid, {"player_id": cid,
                                                     "name": pname,
                                                     "position": info.get("position", "")})
                    row = {
                        "season": season,
                        "week": wk,
                        "team_id": str(e["roster_id"]),
                        "player_id": cid,
                        "player_name": pname,
                        "slot": slot,
                        "is_starter": is_starter,
                        "nfl_team": nfl_team,
                        "points": ppoints.get(pid, 0),
                    }
                    stat_line = map_stat_line(week_stats.get(pid, {}), is_def)
                    for s in stat_fields:
                        row[s] = stat_line.get(s, "")
                    pweeks_rows.append(row)

        # ---- standings ----
        # regular-season place: wins desc, then points-for desc (league convention)
        reg = sorted(rosters,
                     key=lambda r: (-(r["settings"].get("wins") or 0),
                                    -fpts(r["settings"], "fpts")))
        # postseason placement from bracket placement games
        post_rank = {}
        for bracket, base in ((wb, 0), (lb, 6)):
            for g in bracket:
                p = g.get("p")
                if p and g.get("w") is not None:
                    post_rank[str(g["w"])] = base + p
                    post_rank[str(g["l"])] = base + p + 1
        winners_ids = {str(g[k]) for g in wb for k in ("t1", "t2") if g.get(k) is not None}

        for i, r in enumerate(reg, 1):
            st = r["settings"]
            rid = str(r["roster_id"])
            pr = post_rank.get(rid)
            standings_rows.append({
                "season": season,
                "team_id": rid,
                "place": i,
                "record": f"{st.get('wins', 0)}-{st.get('losses', 0)}-{st.get('ties', 0)}",
                "points_for": fpts(st, "fpts"),
                "points_against": fpts(st, "fpts_against"),
                "postseason_rank": pr or "",
                "postseason_label": PLACE_LABELS.get(pr, ""),
                "playoff_bracket": "championship_bracket" if rid in winners_ids else "consolation",
                "mediocre_bowl_total": "",
            })

    return {
        "seasons": seasons,
        "manager_seasons": manager_seasons,
        "manager_names": manager_names,
        "teams": teams_rows,
        "games": games_rows,
        "standings": standings_rows,
        "player_weeks": pweeks_rows,
        "players": players_map,
        "unmatched": unmatched,
    }
