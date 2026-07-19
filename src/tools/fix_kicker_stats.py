#!/usr/bin/env python3
"""
Repair the kicker PAT/FG column swap in existing raw team files.

The scraper mapped NFL.com's grouped-header kicker table wrong: the lone
"Made" column is PAT made, but it was stored as fg_made (pat_made never set).
Distance buckets (fg_0_19 .. fg_50_plus) were parsed correctly.

Deterministic repair for each kicker row that has no pat_made key:
    pat_made = old fg_made
    fg_made  = sum(distance buckets)

Validation: league scoring identity (weights fitted empirically per season —
845/847 rows exact):
    2011:  points == pat*1 + fg(0-39)*3 + fg(40-49)*4 + fg(50+)*5
    2012+: points == pat*1 + fg(0-49)*3 + fg(50+)*5
Rows failing the identity are reported (not blindly trusted).

Run from repo root:  python src/tools/fix_kicker_stats.py [--dry-run]
"""
import argparse
import glob
import json

BUCKETS = ("fg_0_19", "fg_20_29", "fg_30_39", "fg_40_49", "fg_50_plus")


def expected_points(p, season):
    fg_under_50 = (p.get("fg_0_19") or 0) + (p.get("fg_20_29") or 0) + (p.get("fg_30_39") or 0)
    fg_40s = p.get("fg_40_49") or 0
    fg_50 = p.get("fg_50_plus") or 0
    if int(season) <= 2011:
        # distance bonuses: 40-49 = 4, 50+ = 5
        return (p.get("pat_made") or 0) + fg_under_50 * 3 + fg_40s * 4 + fg_50 * 5
    # 2012+: flat 3 for FG under 50, 50+ = 5
    return (p.get("pat_made") or 0) + (fg_under_50 + fg_40s) * 3 + fg_50 * 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    fixed = already = identity_ok = identity_off = 0
    offenders = []
    for path in sorted(glob.glob("data/raw/*/week_*/team_*.json")):
        season = path.split("/")[2]
        with open(path) as f:
            d = json.load(f)
        changed = False
        for p in d.get("players", []):
            if p.get("player_type") != "kicker":
                continue
            if "pat_made" in p:
                already += 1
            else:
                p["pat_made"] = p.get("fg_made") or 0
                p["fg_made"] = sum(p.get(k) or 0 for k in BUCKETS)
                changed = True
                fixed += 1
            exp = expected_points(p, season)
            actual = p.get("fantasy_points") or 0
            if abs(exp - actual) < 0.01:
                identity_ok += 1
            else:
                identity_off += 1
                if len(offenders) < 20:
                    offenders.append((path, p.get("name"), p.get("pat_made"),
                                      p.get("fg_made"), exp, actual))
        if changed and not args.dry_run:
            with open(path, "w") as f:
                json.dump(d, f, indent=2)

    print(f"kicker rows repaired:      {fixed}")
    print(f"already had pat_made:      {already}")
    print(f"scoring identity holds:    {identity_ok}")
    print(f"scoring identity off:      {identity_off}")
    if offenders:
        print("sample identity failures (path, name, pat, fg, expected, actual):")
        for o in offenders:
            print("  ", *o)
    if args.dry_run:
        print("(dry run: no files written)")


if __name__ == "__main__":
    main()
