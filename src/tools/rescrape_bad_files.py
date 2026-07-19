#!/usr/bin/env python3
"""
Parallel re-scrape of broken raw team files, with backup + validation.

A file is "broken" if team_stats is null OR no bench player was detected
(the bench-detection bug that inflates reconstructed totals). Missing files
(schedule expects them but they don't exist) are included only with
--include-missing.

Each scrape uses the working Selenium scraper (api_client_v2_optimized), which
spins up its own headless Chrome and writes its own file, so scrapes run safely
in parallel via a file-level work pool.

Usage (run from repo root):
  python src/tools/rescrape_bad_files.py --seasons 2011 2012 2013 --workers 6
  python src/tools/rescrape_bad_files.py --limit 12 --workers 6      # smoke test
  python src/tools/rescrape_bad_files.py --dry-run                   # just list

Progress lines go to STDERR; the scraper's verbose output goes to STDOUT, so:
  python src/tools/rescrape_bad_files.py ... >detail.log 2>progress.log
"""
import argparse, json, csv, os, shutil, sys, time, random, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, "src")
from ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper

LEAGUE = {"2011": "400491", **{str(y): "864504" for y in range(2012, 2023)}}
RAW = Path("data/raw")
SCHED = Path("data/processed/schedule")
BACKUP = Path("data/raw_backup")

_print_lock = threading.Lock()
def log(msg):
    with _print_lock:
        print(msg, file=sys.stderr, flush=True)


def is_bad(path: Path) -> bool:
    try:
        d = json.load(open(path))
    except Exception:
        return True
    if d.get("team_stats") is None:
        return True
    if not any(p.get("lineup_status") == "bench" for p in d.get("players", [])):
        return True
    return False


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
    work = []
    for season in seasons:
        for wk, tid, pts in schedule_rows(season):
            path = RAW / season / f"week_{int(wk):02d}" / f"team_{tid}.json"
            if not path.exists():
                if include_missing:
                    work.append((season, int(wk), tid, pts))
            elif is_bad(path):
                work.append((season, int(wk), tid, pts))
    return work


def recon(path: Path):
    d = json.load(open(path))
    st = [p for p in d.get("players", [])
          if p.get("lineup_status") == "starter" and p.get("position") != "BN"]
    total = round(sum(float(p.get("fantasy_points") or 0) for p in st), 2)
    nb = sum(1 for p in d.get("players", []) if p.get("lineup_status") == "bench")
    return total, len(st), nb


# One shared scraper instance is safe: get_team_data uses only locals + its own driver.
scraper = NFLFantasyMultiTableScraper()
counter_lock = threading.Lock()
done = 0


def process(item, total_n):
    global done
    season, wk, tid, sched = item
    path = RAW / season / f"week_{wk:02d}" / f"team_{tid}.json"
    result = {"season": season, "week": wk, "team_id": tid, "sched": sched,
              "status": "?", "old": None, "new": None, "starters": None, "bench": None}
    try:
        if path.exists():
            result["old"] = recon(path)[0]
            b = BACKUP / season / f"week_{wk:02d}" / f"team_{tid}.json"
            b.parent.mkdir(parents=True, exist_ok=True)
            if not b.exists():
                shutil.copy2(path, b)
        data = scraper.get_team_data(LEAGUE[season], tid, int(season), wk, force_refresh=True)
        time.sleep(random.uniform(0.3, 1.0))  # politeness jitter
        if data is None or not path.exists():
            result["status"] = "SCRAPE_FAILED"
        else:
            new, ns, nb = recon(path)
            result.update(new=new, starters=ns, bench=nb)
            result["status"] = "match" if abs(new - sched) < 0.5 else "MISMATCH"
    except Exception as e:
        result["status"] = f"ERROR:{type(e).__name__}"
    with counter_lock:
        done += 1
        n = done
    old = result["old"] if result["old"] is not None else 0.0
    new = result["new"] if result["new"] is not None else 0.0
    log(f"[{n}/{total_n}] {season} wk{wk:>2} team{tid:>2} "
        f"sched={sched:>7.2f} old={old:>8.2f} new={new:>7.2f} "
        f"S/B={result['starters']}/{result['bench']} -> {result['status']}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+",
                    default=[str(y) for y in range(2011, 2023)])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of files (smoke test); samples across the worklist")
    ap.add_argument("--include-missing", action="store_true",
                    help="also scrape files the schedule expects but that don't exist")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    work = build_worklist(args.seasons, args.include_missing)
    # deterministic ordering: worst seasons first, then week/team
    work.sort(key=lambda x: (x[0], x[1], x[2]))
    if args.limit and len(work) > args.limit:
        step = len(work) / args.limit
        work = [work[int(i * step)] for i in range(args.limit)]

    from collections import Counter
    by_season = Counter(w[0] for w in work)
    log(f"Worklist: {len(work)} files across {len(by_season)} seasons "
        f"({dict(sorted(by_season.items()))})")
    if args.dry_run:
        for w in work:
            log(f"  would scrape {w[0]} wk{w[1]} team{w[2]} (sched {w[3]})")
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
    fail = [r for r in results if r["status"] not in ("match", "MISMATCH")]
    log("\n===== SUMMARY =====")
    log(f"Scraped {len(results)} files in {dt/60:.1f} min "
        f"({dt/max(len(results),1):.1f}s/file, {args.workers} workers)")
    log(f"  match:    {ok}")
    log(f"  MISMATCH: {len(mis)}")
    log(f"  failed:   {len(fail)}")
    for r in (mis + fail)[:40]:
        log(f"    {r['season']} wk{r['week']} team{r['team_id']} "
            f"sched={r['sched']} new={r['new']} -> {r['status']}")

    # write machine-readable report
    rep = Path("data/metadata/rescrape_report.csv")
    rep.parent.mkdir(parents=True, exist_ok=True)
    with open(rep, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)
    log(f"Report -> {rep}")


if __name__ == "__main__":
    main()
