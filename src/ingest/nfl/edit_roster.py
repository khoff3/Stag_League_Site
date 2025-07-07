#!/usr/bin/env python3
"""
edit_roster.py – one-shot POST to NFL Fantasy “teamHistoryRosterEdit”

$  python edit_roster.py \
       --identity AAABBB.CCCDDD.EEEFFF \
       --ff xyz012ABC \
       --week 16

Requirement:
    pip install requests beautifulsoup4
"""

import argparse, sys, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE  = "https://fantasy.nfl.com/league/864504/history/2012/"
TEAM  = "teamhome?teamId=1&week={week}"
ACTION = (
    "teamHistoryRosterEdit"
    "?gameSeason=2012&leagueId=864504&teamId=1"
)

def scrape_csrf(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    tag  = soup.find("input", {"name": "csrf"})
    if not tag or not tag.get("value"):
        sys.exit("❌  CSRF token not found – are cookies valid?")
    return tag["value"]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--identity", required=True,
                   help="value of nfl-identity cookie")
    p.add_argument("--ff", required=True,
                   help="value of ff cookie (take the *longest* one if several)")
    p.add_argument("--week", type=int, default=16,
                   help="week you’re editing (default 16)")
    args = p.parse_args()

    # ---------- 1  session with cookies ----------
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (RosterEditScript)",
        "Cookie": f"nfl-identity={args.identity}; ff={args.ff}",
    })

    # ---------- 2  GET team page, collect CSRF ----------
    team_url = urljoin(BASE, TEAM.format(week=args.week))
    r = sess.get(team_url, timeout=20)
    if r.status_code // 100 != 2:
        sys.exit(f"❌  GET failed – HTTP {r.status_code}")
    csrf = scrape_csrf(r.text)
    print("✓  CSRF token acquired:", csrf[:10] + "...")

    # ---------- 3  POST form ----------
    payload = {
        "week": args.week,
        "statCategory": "stats",
        "statType": "weekStats",
        "csrf": csrf,
    }
    post_url = urljoin(BASE, ACTION)
    resp = sess.post(post_url, data=payload, timeout=20,
                     allow_redirects=False)

    # ---------- 4  Outcome ----------
    if resp.status_code in (302, 200):
        loc = resp.headers.get("Location", "<none>")
        print(f"✓  POST OK (HTTP {resp.status_code}) – redirected to {loc}")
    elif resp.status_code == 403:
        print("❌  403 Forbidden – likely bad/expired CSRF")
    elif resp.status_code == 302 and "/account/sign-in" in resp.headers.get("Location", ""):
        print("❌  302 → sign-in – cookies invalid / expired")
    else:
        print(f"❌  Unexpected HTTP {resp.status_code}")
        print(resp.text[:500])

if __name__ == "__main__":
    main()
