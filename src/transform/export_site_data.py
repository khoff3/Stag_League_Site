#!/usr/bin/env python3
"""
Export the star-schema data files consumed by the fantasy-league-archive site.

Dimensions:
  managers.csv     one row per human (manager_id = stable NFL.com user_id)
  teams.csv        one row per franchise-season
  players.csv      one row per NFL player appearing in any lineup

Facts:
  games.csv        one row per matchup (regular + playoff, with round/bracket
                   labels and scraped-vs-constructed provenance)
  player_weeks.csv one row per rostered player per team-week, full stat line
  standings.csv    one row per team-season (regular + postseason finish)

Playoff structure:
  brackets/{season}.json  seeded bracket trees (winners/mediocre/toilet)

Inputs: data/processed/schedule/{season}/*, data/raw/{season}/week_NN/team_N.json,
        db_playerids.csv
Output: data/processed/star_schema/

Run from repo root:  python src/transform/export_site_data.py
"""
import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sleeper_star import build_sleeper_rows

ROOT = Path(".")
SCHED = ROOT / "data/processed/schedule"
RAW = ROOT / "data/raw"
OUT = ROOT / "data/processed/star_schema"

SEASONS = sorted(d.name for d in SCHED.iterdir() if d.name.isdigit())

STAT_FIELDS = [
    "passing_yards", "passing_tds", "interceptions",
    "rushing_yards", "rushing_tds",
    "receiving_yards", "receiving_tds",
    "two_point_conversions", "fumbles_lost",
    "fg_made", "fg_0_19", "fg_20_29", "fg_30_39", "fg_40_49", "fg_50_plus", "pat_made",
    "sacks", "fumble_recoveries", "safeties", "def_tds", "points_allowed",
]

SUFFIXES = re.compile(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", re.I)


def norm_name(name: str) -> str:
    n = name.lower().replace(".", "").replace("'", "").strip()
    n = SUFFIXES.sub("", n)
    return re.sub(r"\s+", " ", n)


def load_player_db():
    """merge_name -> list of candidate rows from db_playerids.csv."""
    db = defaultdict(list)
    with open(ROOT / "db_playerids.csv") as f:
        for r in csv.DictReader(f):
            key = norm_name(r.get("merge_name") or r.get("name") or "")
            if key:
                db[key].append(r)
    return db


def pick_player_id(cands, position):
    """Prefer a position match; prefer rows with a gsis_id, then mfl_id."""
    if not cands:
        return None
    pos_matches = [c for c in cands if (c.get("position") or "").upper() == position.upper()]
    pool = pos_matches or cands
    def rank(c):
        return (0 if c.get("gsis_id") not in (None, "", "NA") else 1,
                0 if c.get("mfl_id") not in (None, "", "NA") else 1)
    best = sorted(pool, key=rank)[0]
    for field in ("gsis_id", "mfl_id", "sleeper_id", "espn_id"):
        v = best.get(field)
        if v not in (None, "", "NA"):
            return f"{field.split('_')[0]}:{v}"
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "brackets").mkdir(exist_ok=True)

    # Sleeper era (2023+): same star schema, built from cached API data
    sleeper = build_sleeper_rows(STAT_FIELDS)

    # ---------------- managers + teams ----------------
    managers = {}   # user_id -> {name, seasons:set}
    teams = []
    for season in SEASONS:
        mfile = SCHED / season / "managers.json"
        if not mfile.exists():
            continue
        d = json.load(open(mfile))
        for t in d.values():
            uid = t.get("user_id") or f"unknown_{season}_{t['team_id']}"
            raw_name = t.get("manager_name", "")
            # normalize shouting NFL.com display names (JACOB -> Jacob)
            name = raw_name.title() if raw_name.isupper() else raw_name
            m = managers.setdefault(uid, {"manager_id": uid,
                                          "name": name,
                                          "seasons": set()})
            m["seasons"].add(season)
            teams.append({
                "season": season,
                "team_id": t["team_id"],
                "team_name": t.get("team_name", ""),
                "manager_id": uid,
                "moves": t.get("moves", ""),
                "trades": t.get("trades", ""),
                "waiver_priority": t.get("waiver_priority", ""),
            })

    # merge Sleeper-era manager activity (same canonical ids via crosswalk)
    for mid, sseasons in sleeper["manager_seasons"].items():
        m = managers.setdefault(mid, {"manager_id": mid,
                                      "name": sleeper["manager_names"].get(mid, ""),
                                      "seasons": set()})
        m["seasons"] |= sseasons
    teams.extend(sleeper["teams"])

    with open(OUT / "managers.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["manager_id", "name", "first_season", "last_season", "n_seasons"])
        for m in sorted(managers.values(), key=lambda x: (min(x["seasons"]), x["name"])):
            s = sorted(m["seasons"])
            w.writerow([m["manager_id"], m["name"], s[0], s[-1], len(s)])

    with open(OUT / "teams.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(teams[0].keys()))
        w.writeheader()
        w.writerows(sorted(teams, key=lambda t: (t["season"], int(t["team_id"]))))

    # ---------------- games ----------------
    def fix_semifinal_labels(season_games):
        """The NFL-era bracket builder filed semifinal games under third_place.
        Structural relabel: a winners-bracket game played BEFORE the championship
        whose winner appears in the championship is a semifinal."""
        champ = next((g for g in season_games if g["game_type"] == "championship"), None)
        if not champ:
            return
        champ_week = int(champ["week"])
        champ_teams = {champ["home_team_id"], champ["away_team_id"]}
        for g in season_games:
            if g["game_type"] == "third_place" and int(g["week"]) < champ_week:
                winner = (g["home_team_id"]
                          if float(g["home_points"]) >= float(g["away_points"])
                          else g["away_team_id"])
                if winner in champ_teams:
                    g["game_type"] = "winners"
                    g["round_name"] = "Semifinal"

    games = []
    for season in SEASONS:
        gfile = SCHED / season / "schedule_annotated.csv"
        if not gfile.exists():
            gfile = SCHED / season / "schedule.csv"
        for g in csv.DictReader(open(gfile)):
            is_playoff = str(g.get("is_playoff", "")).lower() == "true"
            bracket = g.get("bracket", "") or ""
            round_name = g.get("playoff_round_name", "") or ""
            if not is_playoff:
                game_type = "regular"
            elif "mediocre" in (bracket + round_name).lower():
                game_type = "mediocre_bowl"
            elif "toilet" in (bracket + round_name).lower() or bracket == "consolation":
                game_type = "toilet_bowl"
            elif "third" in round_name.lower():
                game_type = "third_place"
            elif "championship" in round_name.lower():
                game_type = "championship"
            else:
                game_type = "winners"
            games.append({
                "game_id": g["game_id"],
                "season": season,
                "week": g["week"],
                "home_team_id": g["home_team_id"],
                "away_team_id": g["away_team_id"],
                "home_points": g["home_points"],
                "away_points": g["away_points"],
                "is_playoff": is_playoff,
                "game_type": game_type,
                "round_name": round_name,
                "source": "constructed" if str(g.get("is_simulated", "")).lower() == "true" else "scraped",
            })
    for season in SEASONS:
        fix_semifinal_labels([g for g in games if g["season"] == season])

    # ---- constructed bracket rows are canonical for playoff weeks ----
    # NFL.com couldn't host the league's custom brackets, so the pipeline
    # injected constructed games (suffixed ids like 201914311_toilet_round1)
    # with the REAL pairings; the scraped rows for those teams in those weeks
    # are the platform's meaningless default pairings. Keep constructed rows,
    # drop scraped rows they supersede, then recompute every playoff score
    # from the validated raw player data (constructed rows sometimes carried
    # multi-week aggregates).
    by_week = defaultdict(list)
    for g in games:
        by_week[(g["season"], g["week"])].append(g)
    deduped = []
    seen_pairs = set()
    for rows in by_week.values():
        suffixed = [g for g in rows if "_" in g["game_id"]]
        covered = {t for g in suffixed for t in (g["home_team_id"], g["away_team_id"])}
        for g in rows:
            if "_" not in g["game_id"] and g["home_team_id"] in covered and g["away_team_id"] in covered:
                continue  # superseded by a constructed bracket game
            # drop exact duplicate rows (some scraped schedules repeat a game)
            pair_key = (g["season"], g["week"], frozenset((g["home_team_id"], g["away_team_id"])))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            deduped.append(g)
    games = sorted(deduped, key=lambda g: (g["season"], int(g["week"]), str(g["game_id"])))

    def raw_starter_total(season, week, tid):
        p = RAW / season / f"week_{int(week):02d}" / f"team_{tid}.json"
        if not p.exists():
            return None
        try:
            d = json.load(open(p))
        except Exception:
            return None
        return round(sum(float(x.get("fantasy_points") or 0) for x in d.get("players", [])
                         if x.get("lineup_status") == "starter" and x.get("position") != "BN"), 2)

    for g in games:
        if g["is_playoff"]:
            h = raw_starter_total(g["season"], g["week"], g["home_team_id"])
            a = raw_starter_total(g["season"], g["week"], g["away_team_id"])
            if h is not None:
                g["home_points"] = h
            if a is not None:
                g["away_points"] = a

    games.extend(sleeper["games"])

    # ---- NFL-era playoff reclassification from postseason ranks ----
    # The annotator's labels drifted per era (5-8 bracket games tagged
    # "Mediocre Bowl", the real 2018+ 7v8 Mediocre Bowl series tagged
    # "Consolation", regular wk14 games tagged as playoffs in wk15-start
    # seasons, bottom-bracket games missed entirely). Final standings'
    # postseason ranks are validated, so classify every game in the playoff
    # window from the participants' final ranks instead.
    #
    # Era formats: 2011-2017 wk15-16 with a 4-team winners bracket;
    # 2018-2020 wk14-16 with a 6-team bracket + 7v8 Mediocre Bowl series;
    # 2021-2022 the same shifted to wk15-17.
    post_rank = {}   # (season, team_id) -> postseason rank (inferred if absent)
    n_teams = defaultdict(int)
    for season in SEASONS:
        fs = SCHED / season / "final_standings.json"
        if not fs.exists():
            continue
        rows_fs = json.load(open(fs))
        n_teams[season] = len(rows_fs)
        used, missing = set(), []
        for t in rows_fs:
            tid = str(t["team_id"])
            pr = t.get("postseason_rank")
            if pr:
                post_rank[(season, tid)] = int(pr)
                used.add(int(pr))
            else:
                missing.append((int(t.get("place") or 99), tid))
        # teams the pipeline never placed (e.g. 2016 5th/6th): assign the
        # unused ranks in regular-season order
        for _, tid in sorted(missing):
            r = min(set(range(1, len(rows_fs) + 1)) - used)
            post_rank[(season, tid)] = r
            used.add(r)

    def playoff_window(season):
        y = int(season)
        if 2018 <= y <= 2020:
            return 14, 16
        if y >= 2021:
            return 15, 17
        return 15, 16

    for g in games:
        season = g["season"]
        if season not in n_teams:
            continue  # Sleeper era: already structured from the API bracket
        start, fin = playoff_window(season)
        wk = int(g["week"])
        n = n_teams[season]
        winners_size = 6 if int(season) >= 2018 else 4
        if wk < start:
            g["is_playoff"] = False
            g["game_type"] = "regular"
            g["round_name"] = ""
            continue
        rh = post_rank.get((season, g["home_team_id"]))
        ra = post_rank.get((season, g["away_team_id"]))
        if rh is None or ra is None:
            continue
        pair = {rh, ra}
        g["is_playoff"] = True
        rnd = wk - start + 1
        if max(pair) <= winners_size:
            if wk == fin and pair == {1, 2}:
                g["game_type"], g["round_name"] = "championship", "Championship"
            elif wk == fin and pair == {3, 4}:
                g["game_type"], g["round_name"] = "third_place", "Third Place"
            elif wk == fin:
                g["game_type"], g["round_name"] = "winners", "Fifth Place"
            elif wk == fin - 1:
                g["game_type"], g["round_name"] = "winners", "Semifinal"
            else:
                g["game_type"], g["round_name"] = "winners", "Winners Round 1"
        elif int(season) >= 2018 and pair == {7, 8}:
            g["game_type"], g["round_name"] = "mediocre_bowl", "Mediocre Bowl"
        elif min(pair) > n - 4:
            g["game_type"] = "toilet_bowl"
            if wk == fin and pair == {n - 1, n}:
                g["round_name"] = "Toilet Bowl"
            elif wk == fin:
                g["round_name"] = f"{n - 3}th Place"
            else:
                g["round_name"] = f"Consolation Round {rnd}"
        else:
            g["game_type"] = "consolation"
            if wk == fin and pair == {5, 6}:
                g["round_name"] = "Fifth Place"
            elif wk == fin and pair == {7, 8}:
                g["round_name"] = "7th Place"
            elif wk == fin:
                g["round_name"] = "Consolation"
            else:
                g["round_name"] = f"Consolation Round {rnd}"

    # Sleeper era: keep the bottom-four rule (losers-bracket round 2 games
    # involving byed 7/8 seeds are consolation, not toilet bowl) — mirrors
    # the fork pipeline's update_data.py
    s_places = {(s["season"], str(s["team_id"])): int(s["place"]) for s in sleeper["standings"]}
    s_n = defaultdict(int)
    for s in sleeper["standings"]:
        s_n[s["season"]] += 1
    for g in games:
        if g["season"] in n_teams:
            continue
        if g["game_type"] == "toilet_bowl":
            cutoff = s_n.get(g["season"], 12) - 4
            ph = s_places.get((g["season"], str(g["home_team_id"])), 0)
            pa = s_places.get((g["season"], str(g["away_team_id"])), 0)
            if not (ph > cutoff and pa > cutoff):
                g["game_type"] = "consolation"
                if g["round_name"] in ("", "Toilet Bowl"):
                    g["round_name"] = "Consolation"

    with open(OUT / "games.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(games[0].keys()))
        w.writeheader()
        w.writerows(games)

    # ---------------- standings ----------------
    rows = []
    for season in SEASONS:
        sfile = SCHED / season / "final_standings.json"
        if not sfile.exists():
            continue
        ordinals = {1: "Champion", 2: "Runner Up", 3: "Third Place", 4: "Fourth Place",
                    5: "Fifth Place", 6: "Sixth Place", 7: "Seventh Place", 8: "Eighth Place",
                    9: "Ninth Place", 10: "Tenth Place", 11: "Eleventh Place", 12: "Twelfth Place"}
        for t in json.load(open(sfile)):
            # fall back to the inferred rank when the pipeline never placed a
            # team (e.g. 2016's 5th/6th)
            pr = t.get("postseason_rank") or post_rank.get((season, str(t["team_id"])), "")
            rows.append({
                "season": season,
                "team_id": t["team_id"],
                "place": t.get("place", ""),
                "record": t.get("regular_season_record", ""),
                "points_for": t.get("regular_season_points_for", ""),
                "points_against": t.get("regular_season_points_against", ""),
                "postseason_rank": pr,
                "postseason_label": t.get("postseason_label") or (ordinals.get(pr, "") if pr else ""),
                "playoff_bracket": t.get("playoff_participation", ""),
                "mediocre_bowl_total": t.get("mediocre_bowl_total", ""),
            })
    rows.extend(sleeper["standings"])
    with open(OUT / "standings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---------------- brackets ----------------
    for season in SEASONS:
        b = SCHED / season / "playoff_brackets.json"
        if b.exists():
            shutil.copy2(b, OUT / "brackets" / f"{season}.json")

    # ---------------- players + player_weeks ----------------
    pdb = load_player_db()
    players = {}      # player_id -> {name, position}
    pweeks = []
    unmatched = defaultdict(int)
    skipped_bad = 0

    for season in SEASONS:
        sdir = RAW / season
        if not sdir.exists():
            continue
        for wdir in sorted(sdir.glob("week_*")):
            week = int(wdir.name.split("_")[1])
            for tf in sorted(wdir.glob("team_*.json")):
                team_id = tf.stem.split("_")[1]
                try:
                    d = json.load(open(tf))
                except Exception:
                    skipped_bad += 1
                    continue
                # skip files still exhibiting the bench bug (pre-rescrape)
                if d.get("team_stats") is None:
                    skipped_bad += 1
                    continue
                for p in d.get("players", []):
                    name = p.get("name", "")
                    pos = p.get("position", "")       # slot (QB/RB/W-R/BN/...)
                    ptype = p.get("player_type", "")
                    if ptype == "defense":
                        pid = f"def:{p.get('nfl_team', name)}"
                        players.setdefault(pid, {"player_id": pid, "name": f"{name} DEF",
                                                 "position": "DEF"})
                    else:
                        real_pos = pos if pos != "BN" else ""
                        pid = pick_player_id(pdb.get(norm_name(name)), real_pos or "")
                        if pid is None:
                            pid = f"name:{norm_name(name)}"
                            unmatched[name] += 1
                        entry = players.setdefault(pid, {"player_id": pid, "name": name,
                                                         "position": real_pos})
                        # first sighting may be a bench week (no slot) — backfill
                        # the position once the player shows up in a lineup
                        if not entry["position"] and real_pos and real_pos in (
                                "QB", "RB", "WR", "TE", "K", "DEF"):
                            entry["position"] = real_pos
                        # flex-only/bench-only players: take the position from
                        # the player-id database instead
                        if not entry["position"]:
                            for c in pdb.get(norm_name(name), []):
                                if c.get("position") in ("QB", "RB", "WR", "TE", "K"):
                                    entry["position"] = c["position"]
                                    break
                    row = {
                        "season": season,
                        "week": week,
                        "team_id": team_id,
                        "player_id": pid,
                        "player_name": name,
                        "slot": pos,
                        "is_starter": p.get("lineup_status") == "starter",
                        "nfl_team": p.get("nfl_team", ""),
                        "points": p.get("fantasy_points", 0),
                    }
                    for s in STAT_FIELDS:
                        row[s] = p.get(s, "")
                    pweeks.append(row)

    # merge Sleeper-era players + player-weeks (canonical ids shared across eras)
    for cid, p in sleeper["players"].items():
        players.setdefault(cid, p)
    pweeks.extend(sleeper["player_weeks"])
    for name, count in sleeper["unmatched"].items():
        unmatched[f"[sleeper] {name}"] += count

    with open(OUT / "players.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["player_id", "name", "position"])
        w.writeheader()
        w.writerows(sorted(players.values(), key=lambda x: x["name"]))

    with open(OUT / "player_weeks.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pweeks[0].keys()))
        w.writeheader()
        w.writerows(pweeks)

    # ---------------- summary ----------------
    all_seasons = sorted(set(SEASONS) | set(sleeper["seasons"]))
    print(f"seasons:        {all_seasons[0]}-{all_seasons[-1]} "
          f"(NFL.com {SEASONS[0]}-{SEASONS[-1]}, Sleeper {'/'.join(sleeper['seasons'])})")
    print(f"managers.csv:   {len(managers)} managers")
    print(f"teams.csv:      {len(teams)} team-seasons")
    print(f"games.csv:      {len(games)} games "
          f"({sum(1 for g in games if g['is_playoff'])} playoff, "
          f"{sum(1 for g in games if g['source'] == 'constructed')} constructed)")
    print(f"standings.csv:  {len(rows)} rows")
    print(f"players.csv:    {len(players)} players")
    print(f"player_weeks:   {len(pweeks)} rows "
          f"({sum(1 for r in pweeks if r['is_starter'])} starts)")
    print(f"skipped bad/unfixed raw files: {skipped_bad}")
    if unmatched:
        top = sorted(unmatched.items(), key=lambda x: -x[1])[:15]
        print(f"unmatched player names ({len(unmatched)} distinct, kept with name: ids):")
        for n, c in top:
            print(f"  {c:4}x {n}")
    print(f"\noutput -> {OUT}/")


if __name__ == "__main__":
    main()
