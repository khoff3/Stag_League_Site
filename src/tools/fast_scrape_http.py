#!/usr/bin/env python3
"""
Fast HTTP re-scrape of NFL.com fantasy team-week pages — no Selenium.

The history pages are fully server-rendered, so plain requests + BeautifulSoup
returns the same three player tables the Selenium scraper saw. This reuses the
EXACT parsing methods from api_client_v2_optimized (generic header-based path),
so output files are byte-compatible with the Selenium cache format.

~0.4s/page over HTTP vs ~12s/page via headless Chrome => ~20x throughput.

Selects the same worklist as rescrape_bad_files.py (broken or missing files),
backs up any existing file, validates reconstructed starter totals against
schedule.csv, and writes a report.

Run from repo root:
  python src/tools/fast_scrape_http.py [--include-missing] [--workers 16] [--limit N]
"""
import argparse
import csv
import json
import random
import shutil
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "src")
from ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper

LEAGUE = {"2011": "400491", **{str(y): "864504" for y in range(2012, 2023)}}
RAW = Path("data/raw")
SCHED = Path("data/processed/schedule")
BACKUP = Path("data/raw_backup")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_print_lock = threading.Lock()
_tls = threading.local()

# one parser instance shared for its (stateless) _extract methods
parser = NFLFantasyMultiTableScraper()


def log(msg):
    with _print_lock:
        print(msg, file=sys.stderr, flush=True)


def session():
    if not hasattr(_tls, "s"):
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        _tls.s = s
    return _tls.s


def is_bad(path: Path) -> bool:
    try:
        d = json.load(open(path))
    except Exception:
        return True
    if d.get("team_stats") is None:
        return True
    return not any(p.get("lineup_status") == "bench" for p in d.get("players", []))


def schedule_rows(season: str):
    f = SCHED / season / "schedule.csv"
    if not f.exists():
        return []
    out = []
    for g in csv.DictReader(open(f)):
        out.append((g["week"], g["home_team_id"], float(g["home_points"])))
        out.append((g["week"], g["away_team_id"], float(g["away_points"])))
    return out


def build_worklist(seasons, include_missing):
    work, seen = [], set()
    for season in seasons:
        for wk, tid, pts in schedule_rows(season):
            key = (season, int(wk), tid)
            if key in seen:
                continue
            seen.add(key)
            path = RAW / season / f"week_{int(wk):02d}" / f"team_{tid}.json"
            if not path.exists():
                if include_missing:
                    work.append((season, int(wk), tid, pts))
            elif is_bad(path):
                work.append((season, int(wk), tid, pts))
    return work


def parse_team_page(html: str):
    """Same logic as the Selenium scraper's generic table path."""
    soup = BeautifulSoup(html, "html.parser")
    all_players = []
    for table in soup.find_all("table"):
        all_rows = table.find_all("tr")
        if len(all_rows) < 2:
            continue
        header_row, header_row_index = None, 0
        for row_idx, row in enumerate(all_rows[:2]):
            cells = row.find_all(["th", "td"])
            if cells:
                header_text = " ".join(c.get_text().strip().lower() for c in cells)
                if any(k in header_text for k in ["pos", "position"]):
                    header_row, header_row_index = row, row_idx
                    break
                if any(k in header_text for k in ["offense", "player", "name", "qb", "rb", "wr"]):
                    header_row, header_row_index = row, row_idx
                    break
        if not header_row:
            continue
        headers = [c.get_text().strip().lower() for c in header_row.find_all(["th", "td"])]
        header_text = " ".join(headers)
        if any(w in header_text for w in ["offense", "passing", "rushing", "receiving"]):
            players = parser._extract_offense_data_with_headers(table, headers, header_row_index)
        elif any(w in header_text for w in ["kicker", "pat", "fg made", "0-19", "20-29"]):
            players = parser._extract_kicker_data_with_headers(table, headers, header_row_index)
        elif any(w in header_text for w in ["defense team", "sack", "tackles", "turnover", "int"]):
            players = parser._extract_defense_data_with_headers(table, headers, header_row_index)
        else:
            players = []
        all_players.extend(players)
    return all_players


def recon(players):
    st = [p for p in players
          if p.get("lineup_status") == "starter" and p.get("position") != "BN"]
    nb = sum(1 for p in players if p.get("lineup_status") == "bench")
    total = round(sum(float(p.get("fantasy_points") or 0) for p in st), 2)
    return total, len(st), nb


counter_lock = threading.Lock()
done = 0


def process(item, total_n):
    global done
    season, wk, tid, sched = item
    path = RAW / season / f"week_{wk:02d}" / f"team_{tid}.json"
    result = {"season": season, "week": wk, "team_id": tid, "sched": sched,
              "status": "?", "new": None, "starters": None, "bench": None}
    try:
        url = (f"https://fantasy.nfl.com/league/{LEAGUE[season]}/history/{season}/teamhome"
               f"?statCategory=stats&statSeason={season}&statType=weekStats"
               f"&statWeek={wk}&teamId={tid}&week={wk}")
        r = session().get(url, timeout=30)
        time.sleep(random.uniform(0.05, 0.2))  # politeness jitter
        if r.status_code != 200:
            result["status"] = f"HTTP_{r.status_code}"
        else:
            players = parse_team_page(r.text)
            if not players:
                result["status"] = "NO_PLAYERS"
            else:
                total, ns, nb = recon(players)
                if path.exists():
                    b = BACKUP / season / f"week_{wk:02d}" / f"team_{tid}.json"
                    b.parent.mkdir(parents=True, exist_ok=True)
                    if not b.exists():
                        shutil.copy2(path, b)
                data = {
                    "players": players,
                    "team_stats": {
                        "total_players": len(players),
                        "starters": ns,
                        "bench": nb,
                        "total_points": total,
                    },
                    "source": "html_scraping",
                }
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                result.update(new=total, starters=ns, bench=nb)
                result["status"] = "match" if abs(total - sched) < 0.5 else "MISMATCH"
    except Exception as e:
        result["status"] = f"ERROR:{type(e).__name__}"
    with counter_lock:
        done += 1
        n = done
    if n % 50 == 0 or result["status"] not in ("match",):
        log(f"[{n}/{total_n}] {season} wk{wk:>2} team{tid:>2} "
            f"sched={sched:>7.2f} new={result['new'] if result['new'] is not None else 0:>7.2f} "
            f"S/B={result['starters']}/{result['bench']} -> {result['status']}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", default=[str(y) for y in range(2011, 2023)])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--include-missing", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    work = build_worklist(args.seasons, args.include_missing)
    work.sort(key=lambda x: (x[0], x[1], x[2]))
    if args.limit:
        work = work[:args.limit]
    by_season = Counter(w[0] for w in work)
    log(f"Worklist: {len(work)} files ({dict(sorted(by_season.items()))})")
    if args.dry_run:
        return

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(process, w, len(work)) for w in work]
        for f in as_completed(futs):
            results.append(f.result())

    dt = time.time() - t0
    ok = sum(1 for r in results if r["status"] == "match")
    mis = [r for r in results if r["status"] == "MISMATCH"]
    bad = [r for r in results if r["status"] not in ("match", "MISMATCH")]
    log(f"\n===== SUMMARY =====")
    log(f"{len(results)} files in {dt/60:.1f} min ({dt/max(len(results),1):.2f}s/file, {args.workers} workers)")
    log(f"  match: {ok}  MISMATCH: {len(mis)}  failed: {len(bad)}")
    for r in (mis + bad)[:40]:
        log(f"    {r['season']} wk{r['week']} team{r['team_id']} sched={r['sched']} new={r['new']} -> {r['status']}")

    rep = Path("data/metadata/fast_scrape_report.csv")
    rep.parent.mkdir(parents=True, exist_ok=True)
    with open(rep, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    log(f"Report -> {rep}")


if __name__ == "__main__":
    main()
