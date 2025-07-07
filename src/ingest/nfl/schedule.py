"""
NFL Schedule data collection module.

This module handles fetching and processing NFL schedule data through web scraping.
It includes functionality for:
- Authenticated web scraping of NFL.com
- Processing game data
- Caching results
- Handling rate limiting and retries
"""

import os
import json
import time
import re
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4.element import Tag

# Change from relative import to absolute import
try:
    from .playoff_config import PlayoffConfig
except ImportError:
    # Fallback for direct script execution
    import sys
    sys.path.append(str(Path(__file__).parent))
    from playoff_config import PlayoffConfig

# Load environment variables
load_dotenv()

class NFLScheduleIngest:
    """Handles NFL schedule data ingestion through web scraping."""
    
    def __init__(self):
        """Initialize the NFL Schedule Ingest with configuration and setup."""
        self.base_url = "https://fantasy.nfl.com"
        self.raw_dir = Path("data/raw/schedule")
        self.processed_dir = Path("data/processed/schedule")
        
        # Create data directories if they don't exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure league IDs for different seasons
        self.league_ids = {
            "2011": "400491",  # Original league
            "2012+": "864504"  # New league starting 2012
        }
        
        # Initialize team records
        self._reset_team_records()
        
        # Initialize Selenium WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)
        
        # Initialize regex patterns
        self.team_pattern = re.compile(r'teamId-(\d+).*?teamName">(.*?)</span>.*?teamOwner">(.*?)</span>')
        self.record_pattern = re.compile(r'teamRecord">(.*?)</span>.*?teamRank">\(#(\d+)\)</span>')
        self.streak_pattern = re.compile(r'teamStreak">(.*?)</span>')
        self.waiver_pattern = re.compile(r'teamWaiver">(.*?)</span>')
        
    def fetch_weekly_schedule(self, season: int, week: int, force_refresh: bool = False) -> Dict:
        """
        Fetch schedule data for a specific week using Selenium.
        
        Args:
            season: The NFL season year
            week: The week number (1-18)
            force_refresh: Whether to force a refresh of cached data
            
        Returns:
            Dict containing the schedule data
        """
        if not force_refresh and self._is_cached(season, week):
            return self._load_from_cache(season, week)
            
        league_id = self._get_league_id(str(season))
        
        # Construct URL with all parameters and cache-busting
        base_url = f"{self.base_url}/league/{league_id}/history/{season}/schedule"
        timestamp = int(time.time() * 1000)  # Current timestamp for cache busting
        params = {
            "gameSeason": season,
            "leagueId": league_id,
            "scheduleDetail": week,  # Use the week number directly
            "scheduleType": "week",
            "standingsTab": "schedule",
            "week": week,
            "seasonId": season,
            "_": timestamp  # Cache busting parameter
        }
        
        # Build the full URL with parameters
        url = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        
        try:
            print(f"\nFetching Week {week} schedule...")
            print(f"URL: {url}")
            
            # Add retry logic
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Clear cookies
                    self.driver.delete_all_cookies()
                    
                    # Set user agent
                    self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                        "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    })
                    
                    # Enable network interception
                    self.driver.execute_cdp_cmd('Network.enable', {})
                    
                    # Set cache control headers
                    self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                        'headers': {
                            'Cache-Control': 'no-cache, no-store, must-revalidate',
                            'Pragma': 'no-cache',
                            'Expires': '0'
                        }
                    })
                    
                    # Load the page with cache disabled
                    self.driver.get(url)
                    
                    # Wait for the schedule to load
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "schedule"))
                    )
                    
                    # Wait for dynamic content to load
                    time.sleep(5)
                    
                    # Force a hard refresh (Ctrl+F5 equivalent)
                    self.driver.execute_script("window.location.reload(true);")
                    time.sleep(5)
                    
                    # Wait for team wraps to be present
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "teamWrap"))
                    )
                    
                    # Execute JavaScript to extract data
                    schedule_data = self.driver.execute_script("""
                        var games = [];
                        var teamWraps = document.getElementsByClassName('teamWrap');
                        
                        for (var i = 0; i < teamWraps.length; i += 2) {
                            if (i + 1 >= teamWraps.length) break;
                            
                            var homeWrap = teamWraps[i];
                            var awayWrap = teamWraps[i + 1];
                            
                            var homeTeam = homeWrap.querySelector('.teamName').textContent.trim();
                            var homeId = homeWrap.querySelector('.teamName').className.match(/teamId-(\d+)/)[1];
                            var homePoints = parseFloat(homeWrap.querySelector('.teamTotal').textContent.trim());
                            var homeRecord = homeWrap.querySelector('.teamRecord').textContent.trim();
                            var homeRank = parseInt(homeWrap.querySelector('.teamRank').textContent.match(/\((\d+)\)/)[1]);
                            
                            var awayTeam = awayWrap.querySelector('.teamName').textContent.trim();
                            var awayId = awayWrap.querySelector('.teamName').className.match(/teamId-(\d+)/)[1];
                            var awayPoints = parseFloat(awayWrap.querySelector('.teamTotal').textContent.trim());
                            var awayRecord = awayWrap.querySelector('.teamRecord').textContent.trim();
                            var awayRank = parseInt(awayWrap.querySelector('.teamRank').textContent.match(/\((\d+)\)/)[1]);
                            
                            games.push({
                                game_id: arguments[0] + arguments[1].toString().padStart(2, '0') + homeId + awayId,
                                season: arguments[0],
                                week: arguments[1],
                                home_team: homeTeam,
                                home_team_id: homeId,
                                home_points: homePoints,
                                home_record: homeRecord,
                                home_rank: homeRank,
                                away_team: awayTeam,
                                away_team_id: awayId,
                                away_points: awayPoints,
                                away_record: awayRecord,
                                away_rank: awayRank,
                                scraped_at: new Date().toISOString()
                            });
                        }
                        
                        return { games: games };
                    """, season, week)
                    
                    # Save debug HTML
                    html = self.driver.page_source
                    debug_path = self.raw_dir / f"{season}" / f"week_{week:02d}_debug.html"
                    debug_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(debug_path, 'w') as f:
                        f.write(html)
                    print(f"Saved debug HTML to {debug_path}")
                    
                    # Verify we got different data than before
                    if self._is_cached(season, week):
                        cached_data = self._load_from_cache(season, week)
                        if schedule_data == cached_data:
                            print("Warning: Got identical data after refresh, retrying...")
                            retry_count += 1
                            continue
                    
                    self._save_to_cache(season, week, schedule_data)
                    print(f"✓ Successfully fetched and cached data for Week {week}")
                    return schedule_data
                    
                except TimeoutException:
                    print(f"Timeout while loading page, retry {retry_count + 1}/{max_retries}")
                    retry_count += 1
                    time.sleep(5)
                except Exception as e:
                    print(f"Error fetching data: {str(e)}")
                    retry_count += 1
                    time.sleep(5)
                finally:
                    # Disable network interception
                    self.driver.execute_cdp_cmd('Network.disable', {})
            
            raise Exception(f"Failed to fetch data after {max_retries} retries")
            
        except Exception as e:
            print(f"Error in fetch_weekly_schedule: {str(e)}")
            raise
        
    def _get_league_id(self, season: str) -> str:
        """Get the appropriate league ID for a given season."""
        return self.league_ids.get(season, self.league_ids["2012+"])
        
    def _is_cached(self, season: int, week: int) -> bool:
        """Check if data is cached for a given season and week."""
        cache_path = self.raw_dir / f"{season}" / f"week_{week:02d}.json"
        return cache_path.exists()
        
    def _load_from_cache(self, season: int, week: int) -> Dict:
        """Load cached data for a given season and week."""
        cache_path = self.raw_dir / f"{season}" / f"week_{week:02d}.json"
        print(f"Found cached data for {season} Week {week}")
        print(f"Loading cached data from {cache_path}")
        with open(cache_path, 'r') as f:
            return json.load(f)
        
    def _save_to_cache(self, season: int, week: int, data: Dict):
        """Save data to cache for a given season and week."""
        cache_path = self.raw_dir / f"{season}" / f"week_{week:02d}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saving raw data to {cache_path}")
        
    def close(self):
        """Clean up resources."""
        if hasattr(self, 'driver'):
            self.driver.quit()
        
    def __del__(self):
        """Clean up Selenium WebDriver."""
        if hasattr(self, 'driver'):
            self.driver.quit()
            
    def _get_raw_cache_path(self, season: int, week: int) -> Path:
        """
        Get the raw cache file path for a specific season and week.
        
        Args:
            season: The NFL season year
            week: The week number
            
        Returns:
            Path object for the raw cache file
        """
        return self.raw_dir / f"{season}" / f"week_{week:02d}.json"
        
    def _get_processed_path(self, season: int) -> Path:
        """
        Get the processed data file path for a specific season.
        
        Args:
            season: The NFL season year
            
        Returns:
            Path object for the processed data file
        """
        return self.processed_dir / f"{season}" / "schedule.csv"
        
    def save_processed_data(self, season: int, processed_games: List[Dict]) -> None:
        """
        Save processed schedule data to CSV.
        
        Args:
            season: The NFL season year
            processed_games: List of processed game data
        """
        output_path = self._get_processed_path(season)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Define CSV headers
        headers = [
            "game_id", "season", "week",
            "home_team", "home_team_id", "home_points", "home_record", "home_rank",
            "away_team", "away_team_id", "away_points", "away_record", "away_rank",
            "scraped_at"
        ]
        
        # Write to CSV
        print(f"\nSaving processed data for season {season}")
        print(f"Total games to save: {len(processed_games)}")
        print(f"Output path: {output_path}")
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(processed_games)
            
        print("✓ Successfully saved processed data")
            
    def _reset_team_records(self):
        """Reset the team records tracking for a new season."""
        self.team_records = {}
        
    def _update_team_record(self, team_id: str, points: float, opponent_points: float):
        """Update a team's record based on game result."""
        if team_id not in self.team_records:
            self.team_records[team_id] = {'wins': 0, 'losses': 0, 'ties': 0}
            
        if points > opponent_points:
            self.team_records[team_id]['wins'] += 1
        elif points < opponent_points:
            self.team_records[team_id]['losses'] += 1
        else:
            self.team_records[team_id]['ties'] += 1
            
    def _get_team_record(self, team_id: str) -> str:
        """Get a team's current record in W-L-T format."""
        if team_id not in self.team_records:
            return "0-0-0"
        record = self.team_records[team_id]
        return f"{record['wins']}-{record['losses']}-{record['ties']}"
        
    def _get_team_records_path(self, season: int) -> Path:
        """
        Get the path for team records file for a specific season.
        
        Args:
            season: The NFL season year
            
        Returns:
            Path object for the team records file
        """
        return self.processed_dir / f"{season}" / "team_records.json"
        
    def _save_team_records(self, season: int) -> None:
        """
        Save team records to a JSON file.
        
        Args:
            season: The NFL season year
        """
        records_path = self._get_team_records_path(season)
        records_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Saving team records to {records_path}")
        with open(records_path, 'w') as f:
            json.dump(self.team_records, f, indent=2)
            
    def _load_team_records(self, season: int) -> None:
        """
        Load team records from a JSON file.
        
        Args:
            season: The NFL season year
        """
        records_path = self._get_team_records_path(season)
        if records_path.exists():
            print(f"Loading team records from {records_path}")
            with open(records_path, 'r') as f:
                self.team_records = json.load(f)
        else:
            print(f"No existing team records found for season {season}")
            self._reset_team_records()
            
    def fetch_and_process_week(self, season: int, week: int) -> List[Dict]:
        """
        Fetch and process schedule data for a specific week.
        
        Args:
            season: The NFL season year
            week: The week number
            
        Returns:
            List of processed games for the week
        """
        # Fetch raw data
        raw_data = self.fetch_weekly_schedule(season, week)
        
        # Process the data
        processed_games = self.process_schedule_data(raw_data)
        
        return processed_games
            
    def fetch_and_process_season(self, season: int) -> None:
        """
        Fetch and process schedule data for an entire NFL season.
        
        Args:
            season: The NFL season year
        """
        # Determine max week based on season
        max_week = 17 if season >= 2021 else 16
        
        # Process each week
        all_games = []
        for week in range(1, max_week + 1):
            print(f"\nProcessing Week {week}...")
            
            # Fetch and process the week's data
            games = self.fetch_and_process_week(season, week)
            all_games.extend(games)
            
            # Only update team records for regular season weeks (1-13)
            if week <= 13:
                # Save team records after each regular season week
                self._save_team_records(season)
                print(f"✓ Updated team records (regular season only)")
        
        # Save all games to CSV
        output_path = self._get_processed_path(season)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'game_id', 'season', 'week', 'home_team', 'home_team_id', 
                'home_points', 'home_record', 'home_rank', 'away_team', 
                'away_team_id', 'away_points', 'away_record', 'away_rank',
                'scraped_at'
            ])
            writer.writeheader()
            writer.writerows(all_games)
            
        print(f"\n✓ Processed {len(all_games)} total games")
        print(f"✓ Saved processed data to {output_path}")
        
        # Generate and save playoff brackets
        self.save_playoff_brackets(season)

    def process_schedule_data(self, raw_data: dict) -> list:
        """Process raw schedule data into a list of games."""
        if not raw_data or 'games' not in raw_data:
            return []
        processed_games = []
        for game in raw_data['games']:
            # Use the records as scraped from the HTML (do not recalculate)
            # Just pass through the home_record and away_record fields
            processed_games.append(game)
        return processed_games

    def _extract_teams_data(self, text: str) -> List[Dict]:
        """
        Extract team data from text using regex patterns.
        
        Args:
            text: The text to extract data from
            
        Returns:
            List of dictionaries containing team data
        """
        teams = []
        if not text:
            return teams
        # Find all team matches
        team_matches = list(self.patterns['team_link'].finditer(text))
        record_matches = list(self.patterns['record_rank'].finditer(text))
        streak_matches = list(self.patterns['streak'].finditer(text))
        waiver_matches = list(self.patterns['waiver'].finditer(text))
        # Process each team
        for i in range(len(team_matches)):
            team_match = team_matches[i]
            record_match = record_matches[i] if i < len(record_matches) else None
            streak_match = streak_matches[i] if i < len(streak_matches) else None
            waiver_match = waiver_matches[i] if i < len(waiver_matches) else None
            team_data = {
                'team_name': team_match.group(1),
                'team_id': team_match.group(2),
                'owner': team_match.group(3),
                'record': record_match.group(1) if record_match else "0-0-0",
                'rank': int(record_match.group(2)) if record_match else 0,
                'streak': streak_match.group(1) if streak_match else None,
                'waiver': float(waiver_match.group(1)) if waiver_match else None
            }
            teams.append(team_data)
        return teams 

    def _detect_division_based_seeding(self, team_records: Dict, playoff_games: List[Dict], season: int) -> tuple:
        """
        Detect division-based playoff seeding from actual playoff schedule.
        
        Args:
            team_records: Dict of team records
            playoff_games: List of playoff games
            season: The NFL season year
            
        Returns:
            Tuple of (winners_teams, middle_teams, consolation_teams) with division-based seeding
        """
        # Get Week 15 playoff games to determine seeding
        week15_games = [g for g in playoff_games if int(g['week']) == 15]
        
        # Extract teams that play in Week 15
        week15_teams = set()
        for game in week15_games:
            week15_teams.add(game['home_team_id'])
            week15_teams.add(game['away_team_id'])
        
        # Sort teams by record (wins, then points scored for tie-breaking)
        sorted_teams = sorted(
            team_records.items(),
            key=lambda x: (x[1]['wins'], x[1]['losses'], x[1].get('points_for', 0)),
            reverse=True
        )
        
        # For 2013-2015, the actual playoff structure was:
        # - Top 4 teams by record were in the winners bracket
        # - Next 4 teams were in the middle teams bracket (mediocre bowl)
        # - Bottom 4 teams were in consolation (toilet bowl)
        
        # But the seeding within each bracket was division-based
        # So we need to look at the actual Week 15 matchups to determine the correct seeding
        
        # Build teams lists based on actual Week 15 participation
        winners_teams = []
        middle_teams = []
        consolation_teams = []
        
        # First, identify which teams are in Week 15 (these are the playoff teams)
        playoff_team_ids = set()
        for game in week15_games:
            playoff_team_ids.add(game['home_team_id'])
            playoff_team_ids.add(game['away_team_id'])
        
        # Teams not in Week 15 are consolation teams
        for team_id, data in sorted_teams:
            if team_id not in playoff_team_ids:
                consolation_teams.append((team_id, data))
        
        # For teams in Week 15, we need to determine winners vs middle teams
        # Look at the actual matchups to determine seeding
        week15_team_ids = list(playoff_team_ids)
        
        # For 2013, we know the actual structure from the data:
        if season == 2013:
            # Winners bracket teams (from actual Week 15 games):
            # Charles in Charge (2) vs For Whom Le'Veon Bell Tolls (5)
            # TA-VON-ME (4) vs Colin The Shots (1)
            winners_ids = {'2', '5', '4', '1'}  # Charles, For Whom, TA-VON-ME, Colin
            
            # Middle teams (from actual Week 15 games):
            # Marshall Law (8) vs The Green Machine (11)
            # MONDAY Night MURDERERS (6) vs Bearing Down (7)
            middle_ids = {'8', '11', '6', '7'}  # Marshall, Green Machine, MONDAY, Bearing
            
            # Consolation teams (not in Week 15)
            consolation_ids = set()
            
        elif season == 2014:
            # Winners bracket teams (from actual Week 15 games):
            # Forte's Foreplay (10) vs My Dinner with Andre (5)
            # Stills Harvin Some Woodhead (3) vs InstaGraham (1)
            winners_ids = {'10', '5', '3', '1'}  # Forte's, My Dinner, Stills, InstaGraham
            
            # Middle teams (from actual Week 15 games):
            # SweatyandEddiesQuestfortheStag (6) vs Christopher Welken (11)
            # Knowshon's Eleven (7) vs Chuck-E-Brees (9)
            middle_ids = {'6', '11', '7', '9'}  # Sweaty, Christopher, Knowshon, Chuck-E
            
            # Consolation teams (not in Week 15)
            consolation_ids = set()
            
        elif season == 2015:
            # Winners bracket teams (from actual Week 15 games):
            # Guardians of the Gostkowski (1) vs Mange and Julio DBTSY (3)
            # The Iron Bryants (6) vs Keenan and Dion Memorial Squad (5)
            winners_ids = {'1', '3', '6', '5'}  # Guardians, Mange, Iron Bryants, Keenan
            
            # Middle teams (from actual Week 15 games):
            # The Walking Dead (7) vs Cole's Drafted Players (10)
            # MI6 Quest for the Repeat (2) vs Cooper Scoopers (9)
            middle_ids = {'7', '10', '2', '9'}  # Walking Dead, Cole's, MI6, Cooper
            
            # Consolation teams (not in Week 15)
            consolation_ids = set()
        
        elif season == 2017:
            # 2017: 10-team format with divisions - implement division-based seeding
            # Based on the actual Week 15-16 games:
            # Winners bracket (seeds 1-4): Ultralight Kareem, Roaring Rivers, Hooked on a Thielen, New Gurley
            # Mediocre bowl (seeds 5-6): Nuthin but a Green Thang, Allen the Family
            # Toilet bowl (seeds 7-10): O Beckham Where Art Thou, Suicide Squad, Diggs It, Don't Check My Pryors
            
            # Extract teams from Week 15 winners bracket games
            winners_ids = set()
            middle_ids = set()
            consolation_ids = set()
            
            # Winners bracket teams (from Week 15 winners bracket games)
            winners_ids = {'5', '6', '12', '7'}  # Ultralight Kareem, Roaring Rivers, Hooked on a Thielen, New Gurley
            
            # Middle teams (from Week 16 mediocre bowl game)
            middle_ids = {'1', '3'}  # Nuthin but a Green Thang, Allen the Family
            
            # Toilet bowl teams (from Week 15 toilet bowl games)
            consolation_ids = {'8', '11', '9', '2'}  # O Beckham Where Art Thou, Suicide Squad, Diggs It, Don't Check My Pryors
        
        else:
            # Fallback to standard logic for 2018+ and other seasons
            # Use regular season standings to determine bracket assignments
            winners_ids = set()
            middle_ids = set()
            consolation_ids = set()
            
            # For 2018+: Top 6 teams go to winners bracket, next 2 to mediocre bowl, bottom 4 to toilet bowl
            if season >= 2018:
                # Top 6 teams by record go to winners bracket
                for i, (team_id, _) in enumerate(sorted_teams[:6]):
                    winners_ids.add(team_id)
                # Next 2 teams go to mediocre bowl
                for i, (team_id, _) in enumerate(sorted_teams[6:8]):
                    middle_ids.add(team_id)
                # Bottom 4 teams go to toilet bowl
                for i, (team_id, _) in enumerate(sorted_teams[8:]):
                    consolation_ids.add(team_id)
            else:
                # For older seasons, use the original logic
                winners_ids = set(week15_team_ids[:4])
                middle_ids = set(week15_team_ids[4:])
                consolation_ids = set()  # Empty set for fallback case
        
        # Assign teams to brackets based on actual seeding
        for team_id, data in sorted_teams:
            if team_id in winners_ids:
                winners_teams.append((team_id, data))
            elif team_id in middle_ids:
                middle_teams.append((team_id, data))
            elif team_id in consolation_ids:
                consolation_teams.append((team_id, data))
            elif team_id not in playoff_team_ids:
                consolation_teams.append((team_id, data))
        
        print(f"Detected division-based seeding for {season}:")
        print(f"  Winners bracket: {[data['team_name'] for _, data in winners_teams]}")
        print(f"  Middle teams: {[data['team_name'] for _, data in middle_teams]}")
        print(f"  Consolation: {[data['team_name'] for _, data in consolation_teams]}")
        
        return winners_teams, middle_teams, consolation_teams

    def _get_playoff_teams(self, team_records: Dict, season: int, playoff_games: List[Dict] = None) -> tuple:
        """
        Determine playoff teams based on season format.
        
        Args:
            team_records: Dict of team records
            season: The NFL season year
            playoff_games: List of playoff games (for division-based seeding detection)
            
        Returns:
            Tuple of (winners_teams, middle_teams, consolation_teams)
        """
        config = PlayoffConfig.get_config(season)
        
        # Sort teams by win percentage, then points scored for tie-breaking
        def win_pct(data):
            games = data['wins'] + data['losses'] + data['ties']
            return (data['wins'] + 0.5 * data['ties']) / games if games > 0 else 0
        sorted_teams = sorted(
            team_records.items(),
            key=lambda x: (win_pct(x[1]), x[1].get('points_for', 0)),
            reverse=True
        )
        
        if season <= 2012:
            # 2011-2012: Top 4 in winners, bottom 8 in consolation
            winners_teams = sorted_teams[:4]
            middle_teams = []
            consolation_teams = sorted_teams[4:]
            
        elif season <= 2015:
            # 2013-2015: Use division-based seeding detection if playoff games are available
            if playoff_games:
                return self._detect_division_based_seeding(team_records, playoff_games, season)
            else:
                # Fallback to standard logic if no playoff games available
                winners_teams = sorted_teams[:4]  # Top 4 overall
                middle_teams = sorted_teams[4:8]  # Seeds 5-8
                consolation_teams = sorted_teams[8:]  # Seeds 9-12
            
        elif season == 2017:
            # 2017: 10-team format with divisions - use division-based seeding detection
            if playoff_games:
                return self._detect_division_based_seeding(team_records, playoff_games, season)
            else:
                # Fallback to standard logic if no playoff games available
                winners_teams = sorted_teams[:4]  # Seeds 1-4
                middle_teams = sorted_teams[4:6]  # Seeds 5-6 (mediocre bowl)
                consolation_teams = sorted_teams[6:]  # Seeds 7-10 (toilet bowl)
        
        elif season == 2017:
            # 2017: 10-team format with divisions - use division-based seeding detection
            if playoff_games:
                return self._detect_division_based_seeding(team_records, playoff_games, season)
            else:
                # Fallback to standard logic if no playoff games available
                winners_teams = sorted_teams[:4]  # Seeds 1-4
                middle_teams = sorted_teams[4:6]  # Seeds 5-6 (mediocre bowl)
                consolation_teams = sorted_teams[6:]  # Seeds 7-10 (toilet bowl)
        
        else:
            # 2016-2017: Top 6 in winners bracket, bottom 6 in consolation
            if season <= 2017:
                winners_teams = sorted_teams[:6]
                middle_teams = []
                consolation_teams = sorted_teams[6:]
            else:
                # 2018+: Top 6 in winners bracket, next 2 in middle teams, bottom 4 in consolation
                winners_teams = sorted_teams[:6]
                middle_teams = sorted_teams[6:8]  # Seeds 7-8
                consolation_teams = sorted_teams[8:]  # Seeds 9-12
                

            
        return winners_teams, middle_teams, consolation_teams

    def generate_playoff_brackets(self, season: int) -> Dict:
        """
        Generate playoff brackets (winners and consolation) from schedule data.
        
        Args:
            season: The NFL season year
            
        Returns:
            Dict containing the playoff brackets structure
        """
        # Get playoff configuration for the season
        config = PlayoffConfig.get_config(season)
        
        # Load the schedule data
        schedule_path = self._get_processed_path(season)
        if not schedule_path.exists():
            raise FileNotFoundError(f"No schedule data found for season {season}")
            
        # Read the CSV
        games = []
        with open(schedule_path, 'r') as f:
            reader = csv.DictReader(f)
            games = list(reader)
            
        # Get regular season standings (weeks 1-14) - CALCULATE FROM GAME RESULTS
        regular_season_games = [g for g in games if int(g['week']) <= config.regular_season_weeks]
        team_records = {}
        
        # Calculate regular season records from actual game results
        for game in regular_season_games:
            home_id = game['home_team_id']
            away_id = game['away_team_id']
            home_points = float(game['home_points'])
            away_points = float(game['away_points'])
            
            # Initialize records if needed
            if home_id not in team_records:
                team_records[home_id] = {'wins': 0, 'losses': 0, 'ties': 0, 'team_name': game['home_team'], 'points_for': 0}
            if away_id not in team_records:
                team_records[away_id] = {'wins': 0, 'losses': 0, 'ties': 0, 'team_name': game['away_team'], 'points_for': 0}
                
            # Update records based on actual game results
            if home_points > away_points:
                team_records[home_id]['wins'] += 1
                team_records[away_id]['losses'] += 1
            elif home_points < away_points:
                team_records[home_id]['losses'] += 1
                team_records[away_id]['wins'] += 1
            else:
                team_records[home_id]['ties'] += 1
                team_records[away_id]['ties'] += 1
            
            # Add points scored
            team_records[home_id]['points_for'] += home_points
            team_records[away_id]['points_for'] += away_points
        
        # Debug: Print Granger Danger's game-by-game results
        granger_games = [g for g in regular_season_games if g['home_team_id'] == '2' or g['away_team_id'] == '2']
        print(f"\nGranger Danger (Team ID: 2) game-by-game results:")
        for game in granger_games:
            week = game['week']
            home_id = game['home_team_id']
            away_id = game['away_team_id']
            home_points = float(game['home_points'])
            away_points = float(game['away_points'])
            
            if home_id == '2':
                opponent = game['away_team']
                granger_points = home_points
                opponent_points = away_points
                result = "W" if home_points > away_points else "L"
            else:
                opponent = game['home_team']
                granger_points = away_points
                opponent_points = home_points
                result = "W" if away_points > home_points else "L"
                
            print(f"  Week {week}: vs {opponent} - {granger_points:.1f} to {opponent_points:.1f} ({result})")
        
        print(f"Final record: {team_records['2']['wins']}-{team_records['2']['losses']}-{team_records['2']['ties']}")
                
        # Get playoff games
        playoff_games = [g for g in games if config.playoff_start_week <= int(g['week']) <= config.playoff_end_week]
                
        # Get playoff teams based on season format
        winners_teams, middle_teams, consolation_teams = self._get_playoff_teams(team_records, season, playoff_games)
        
        print(f"\nCalculated regular season standings for {season}:")
        for i, (team_id, data) in enumerate(winners_teams + middle_teams + consolation_teams, 1):
            print(f"{i}. {data['team_name']} ({data['wins']}-{data['losses']}-{data['ties']})")
        
        # Initialize bracket structure
        brackets = {
            'winners_bracket': {
                'round_1': [],  # Week 15 (or 14 for 2016+)
                'championship_week': {  # Week 16 (or 15-16 for 2016+)
                    game_type: [] for game_type in config.championship_week_games.keys()
                    if game_type != 'toilet_bowl'
                }
            },
            'middle_teams_bracket': {
                'round_1': [],  # Week 15 mediocre bowl games
                'mediocre_bowl': []  # Week 16 mediocre bowl games
            },
            'consolation_bracket': {
                'round_1': [],  # Week 15 toilet bowl games (conceptual)
                'toilet_bowl': []  # Week 16 toilet bowl games (conceptual)
            }
        }
        
        # Add middle teams if they exist (2013-2015)
        if middle_teams:
            brackets['middle_teams'] = [
                {
                    'seed': i+5,  # Seeds 5-8
                    'team_id': team_id,
                    'team_name': data['team_name'],
                    'record': f"{data['wins']}-{data['losses']}-{data['ties']}"
                }
                for i, (team_id, data) in enumerate(middle_teams)
            ]
        
        # Process playoff games by week
        semifinal_winners = []
        semifinal_losers = []
        semifinal_games = []
        for week in range(config.playoff_start_week, config.playoff_end_week + 1):
            week_games = [g for g in playoff_games if int(g['week']) == week]
            for game in week_games:
                game_data = {
                    'game_id': game['game_id'],
                    'home_team': {
                        'id': game['home_team_id'],
                        'name': game['home_team'],
                        'points': float(game['home_points'])
                    },
                    'away_team': {
                        'id': game['away_team_id'],
                        'name': game['away_team'],
                        'points': float(game['away_points'])
                    },
                    'winner': game['home_team_id'] if float(game['home_points']) > float(game['away_points']) else game['away_team_id']
                }
                # Determine which bracket this game belongs to
                home_seed = next((i+1 for i, (team_id, _) in enumerate(winners_teams) if team_id == game['home_team_id']), None)
                away_seed = next((i+1 for i, (team_id, _) in enumerate(winners_teams) if team_id == game['away_team_id']), None)
                
                # Check if teams are middle teams (seeds 5-8)
                home_middle = next((i+5 for i, (team_id, _) in enumerate(middle_teams) if team_id == game['home_team_id']), None)
                away_middle = next((i+5 for i, (team_id, _) in enumerate(middle_teams) if team_id == game['away_team_id']), None)
                
                # Check if teams are consolation teams (seeds 9-12)
                home_consolation = next((i+9 for i, (team_id, _) in enumerate(consolation_teams) if team_id == game['home_team_id']), None)
                away_consolation = next((i+9 for i, (team_id, _) in enumerate(consolation_teams) if team_id == game['away_team_id']), None)
                
                # DEBUG: Print game identification
                if home_seed is not None or away_seed is not None:
                    print(f"DEBUG: Week {week} - {game['home_team']} (seed {home_seed}) vs {game['away_team']} (seed {away_seed})")
                
                if home_seed is not None and away_seed is not None:
                    # This is a winners bracket game
                    if week == config.playoff_start_week:
                        brackets['winners_bracket']['round_1'].append(game_data)
                        # Track for championship/third place assignment
                        semifinal_games.append(game_data)
                    else:  # championship week
                        # For 2013-2015, assign championship/third place based on semifinal results
                        if season <= 2015:
                            # Find the two semifinal games from week 15
                            if len(semifinal_games) == 2:
                                # Get winners and losers from week 15
                                for sg in semifinal_games:
                                    winner_id = sg['winner']
                                    loser_id = sg['home_team']['id'] if sg['winner'] == sg['away_team']['id'] else sg['away_team']['id']
                                    semifinal_winners.append(winner_id)
                                    semifinal_losers.append(loser_id)
                                # Now, for week 16, assign games
                                if (game['home_team_id'] in semifinal_winners and game['away_team_id'] in semifinal_winners):
                                    brackets['winners_bracket']['championship_week']['championship'].append(game_data)
                                elif (game['home_team_id'] in semifinal_losers and game['away_team_id'] in semifinal_losers):
                                    brackets['winners_bracket']['championship_week']['third_place'].append(game_data)
                                else:
                                    brackets['winners_bracket']['championship_week']['consolation'].append(game_data)
                                continue
                        # For 2016+, handle the new format with byes
                        elif season >= 2016:
                            # For 2016+, the structure is:
                            # Week 14: Round 1 (seeds 3v6, 4v5)
                            # Week 15: Semifinals (winners of round 1 vs seeds 1-2)
                            # Week 16: Championship and third place
                            if week == config.playoff_start_week:  # Week 14 (round 1)
                                # Track round 1 results
                                semifinal_games.append(game_data)
                                winner_id = game_data['winner']
                                loser_id = game_data['home_team']['id'] if game_data['winner'] == game_data['away_team']['id'] else game_data['away_team']['id']
                                semifinal_winners.append(winner_id)
                                semifinal_losers.append(loser_id)
                                # Put round 1 games in round_1
                                brackets['winners_bracket']['round_1'].append(game_data)
                            elif week == config.playoff_start_week + 1:  # Week 15 (semifinals)
                                # Track semifinal results - these are the actual semifinal winners/losers
                                semifinal_games.append(game_data)
                                winner_id = game_data['winner']
                                loser_id = game_data['home_team']['id'] if game_data['winner'] == game_data['away_team']['id'] else game_data['away_team']['id']
                                # Add to semifinal winners/losers lists (don't clear, accumulate)
                                semifinal_winners.append(winner_id)
                                semifinal_losers.append(loser_id)
                                # Put semifinal games in third_place for now (will be corrected in week 16)
                                brackets['winners_bracket']['championship_week']['third_place'].append(game_data)
                            elif week == config.playoff_end_week:  # Week 16 (championship/third place/5th place)
                                # Now assign based on semifinal results
                                if (game['home_team_id'] in semifinal_winners and game['away_team_id'] in semifinal_winners):
                                    brackets['winners_bracket']['championship_week']['championship'].append(game_data)
                                elif (game['home_team_id'] in semifinal_losers and game['away_team_id'] in semifinal_losers):
                                    brackets['winners_bracket']['championship_week']['third_place'].append(game_data)
                                else:
                                    # If both teams are round 1 losers, this is a 5th place game
                                    round1_loser_ids = [g['home_team']['id'] if g['winner'] == g['away_team']['id'] else g['away_team']['id'] for g in brackets['winners_bracket']['round_1']]
                                    if game['home_team_id'] in round1_loser_ids and game['away_team_id'] in round1_loser_ids:
                                        brackets['winners_bracket']['championship_week']['fifth_place'].append(game_data)
                                    else:
                                        # Mixed game (should not happen)
                                        brackets['winners_bracket']['championship_week']['consolation'].append(game_data)
                            continue
                        # Fallback to old logic if not 2013-2015 or 2016+
                        if home_seed <= 2 and away_seed <= 2:
                            brackets['winners_bracket']['championship_week']['championship'].append(game_data)
                        elif home_seed <= 4 and away_seed <= 4:
                            brackets['winners_bracket']['championship_week']['third_place'].append(game_data)
                        else:
                            brackets['winners_bracket']['championship_week']['consolation'].append(game_data)
                elif home_middle is not None and away_middle is not None:
                    # This is a middle teams game (mediocre bowl)
                    if week == config.playoff_start_week:
                        brackets['middle_teams_bracket']['round_1'].append(game_data)
                    else:  # championship week
                        # For middle teams, this should be mediocre bowl, not toilet bowl
                        # We'll handle this in the playoff annotation script
                        brackets['middle_teams_bracket']['mediocre_bowl'].append(game_data)
                elif home_consolation is not None and away_consolation is not None:
                    # This is a consolation bracket game (toilet bowl)
                    if week == config.playoff_start_week:
                        brackets['consolation_bracket']['round_1'].append(game_data)
                    else:  # championship week
                        brackets['consolation_bracket']['toilet_bowl'].append(game_data)
        
        # Add missing toilet bowl games for consolation teams if they don't exist
        if season <= 2015 and consolation_teams and len(consolation_teams) >= 4:
            # Check if we have toilet bowl games
            existing_toilet_games = brackets['consolation_bracket']['toilet_bowl']
            consolation_team_ids = [team_id for team_id, _ in consolation_teams]
            
            # Note: Consolation teams (seeds 9-12) don't actually play games in NFL Fantasy
            # But we simulate a single-elimination toilet bowl tournament
            # Goal: Find the "ultimate loser" who loses both games
            if not existing_toilet_games:
                print(f"Simulating toilet bowl tournament for consolation teams {consolation_team_ids}")
                print(f"Single-elimination format: losers advance to play each other")
                
                # Create simulated toilet bowl games for single-elimination tournament
                if len(consolation_teams) >= 4:
                    # Seed 9 vs Seed 12, Seed 10 vs Seed 11
                    team9_id, team9_data = consolation_teams[0]  # Seed 9
                    team10_id, team10_data = consolation_teams[1]  # Seed 10
                    team11_id, team11_data = consolation_teams[2]  # Seed 11
                    team12_id, team12_data = consolation_teams[3]  # Seed 12
                    
                    # Week 15: First round of toilet bowl (single elimination)
                    # In toilet bowl, LOSERS advance to play each other
                    week15_game1 = {
                        'game_id': f"{season}15{team9_id}{team12_id}_toilet",
                        'home_team': {
                            'id': team9_id,
                            'name': team9_data['team_name'],
                            'points': 85.0  # Simulated score
                        },
                        'away_team': {
                            'id': team12_id,
                            'name': team12_data['team_name'],
                            'points': 75.0  # Simulated score
                        },
                        'winner': team9_id,  # Seed 9 wins, Seed 12 loses and advances
                        'note': 'Toilet bowl: Seed 12 loses and advances to losers bracket'
                    }
                    brackets['consolation_bracket']['round_1'].append(week15_game1)
                    
                    week15_game2 = {
                        'game_id': f"{season}15{team10_id}{team11_id}_toilet",
                        'home_team': {
                            'id': team10_id,
                            'name': team10_data['team_name'],
                            'points': 82.0  # Simulated score
                        },
                        'away_team': {
                            'id': team11_id,
                            'name': team11_data['team_name'],
                            'points': 78.0  # Simulated score
                        },
                        'winner': team10_id,  # Seed 10 wins, Seed 11 loses and advances
                        'note': 'Toilet bowl: Seed 11 loses and advances to losers bracket'
                    }
                    brackets['consolation_bracket']['round_1'].append(week15_game2)
                
                # Week 16: Losers bracket (the teams that lost Week 15 play each other)
                # The loser of this game is the "ultimate loser" (12th place)
                if len(consolation_teams) >= 4:
                    # Week 16: Losers bracket (11th place game)
                    # Seed 12 vs Seed 11 (both lost in Week 15)
                    week16_losers_game = {
                        'game_id': f"{season}16{team12_id}{team11_id}_toilet",
                        'home_team': {
                            'id': team12_id,
                            'name': team12_data['team_name'],
                            'points': 70.0  # Simulated score
                        },
                        'away_team': {
                            'id': team11_id,
                            'name': team11_data['team_name'],
                            'points': 75.0  # Simulated score
                        },
                        'winner': team11_id,  # Seed 11 wins, Seed 12 loses (ultimate loser)
                        'note': 'Toilet bowl losers bracket: Seed 12 loses both games = 12th place'
                    }
                    brackets['consolation_bracket']['toilet_bowl'].append(week16_losers_game)
                    
                    # Week 16: Winners bracket (9th place game)
                    # Seed 9 vs Seed 10 (both won in Week 15)
                    week16_winners_game = {
                        'game_id': f"{season}16{team9_id}{team10_id}_toilet",
                        'home_team': {
                            'id': team9_id,
                            'name': team9_data['team_name'],
                            'points': 88.0  # Simulated score
                        },
                        'away_team': {
                            'id': team10_id,
                            'name': team10_data['team_name'],
                            'points': 85.0  # Simulated score
                        },
                        'winner': team9_id,  # Seed 9 wins (9th place)
                        'note': 'Toilet bowl winners bracket: Seed 9 wins = 9th place'
                    }
                    brackets['consolation_bracket']['toilet_bowl'].append(week16_winners_game)
        
        # Add toilet bowl simulation for 2017 format (seeds 7-10)
        if season == 2017 and consolation_teams and len(consolation_teams) >= 4:
            # Check if we have toilet bowl games
            existing_toilet_games = brackets['consolation_bracket']['toilet_bowl']
            consolation_team_ids = [team_id for team_id, _ in consolation_teams]
            
            if not existing_toilet_games:
                print(f"Simulating toilet bowl tournament for 2017 consolation teams {consolation_team_ids}")
                print(f"Single-elimination format: losers advance to play each other")
                
                # Create simulated toilet bowl games for single-elimination tournament
                if len(consolation_teams) >= 4:
                    # Seed 7 vs Seed 10, Seed 8 vs Seed 9
                    team7_id, team7_data = consolation_teams[0]  # Seed 7
                    team8_id, team8_data = consolation_teams[1]  # Seed 8
                    team9_id, team9_data = consolation_teams[2]  # Seed 9
                    team10_id, team10_data = consolation_teams[3]  # Seed 10
                    
                    # Week 15: First round of toilet bowl (single elimination)
                    # In toilet bowl, LOSERS advance to play each other
                    week15_game1 = {
                        'game_id': f"{season}15{team7_id}{team10_id}_toilet",
                        'home_team': {
                            'id': team7_id,
                            'name': team7_data['team_name'],
                            'points': 85.0  # Simulated score
                        },
                        'away_team': {
                            'id': team10_id,
                            'name': team10_data['team_name'],
                            'points': 75.0  # Simulated score
                        },
                        'winner': team7_id,  # Seed 7 wins, Seed 10 loses and advances
                        'note': 'Toilet bowl: Seed 10 loses and advances to losers bracket'
                    }
                    brackets['consolation_bracket']['round_1'].append(week15_game1)
                    
                    week15_game2 = {
                        'game_id': f"{season}15{team8_id}{team9_id}_toilet",
                        'home_team': {
                            'id': team8_id,
                            'name': team8_data['team_name'],
                            'points': 82.0  # Simulated score
                        },
                        'away_team': {
                            'id': team9_id,
                            'name': team9_data['team_name'],
                            'points': 78.0  # Simulated score
                        },
                        'winner': team8_id,  # Seed 8 wins, Seed 9 loses and advances
                        'note': 'Toilet bowl: Seed 9 loses and advances to losers bracket'
                    }
                    brackets['consolation_bracket']['round_1'].append(week15_game2)
                
                # Week 16: Losers bracket (the teams that lost Week 15 play each other)
                # The loser of this game is the "ultimate loser" (10th place)
                if len(consolation_teams) >= 4:
                    # Week 16: Losers bracket (9th place game)
                    # Seed 10 vs Seed 9 (both lost in Week 15)
                    week16_losers_game = {
                        'game_id': f"{season}16{team10_id}{team9_id}_toilet",
                        'home_team': {
                            'id': team10_id,
                            'name': team10_data['team_name'],
                            'points': 70.0  # Simulated score
                        },
                        'away_team': {
                            'id': team9_id,
                            'name': team9_data['team_name'],
                            'points': 75.0  # Simulated score
                        },
                        'winner': team9_id,  # Seed 9 wins, Seed 10 loses (ultimate loser)
                        'note': 'Toilet bowl losers bracket: Seed 10 loses both games = 10th place'
                    }
                    brackets['consolation_bracket']['toilet_bowl'].append(week16_losers_game)
                    
                    # Week 16: Winners bracket (7th place game)
                    # Seed 7 vs Seed 8 (both won in Week 15)
                    week16_winners_game = {
                        'game_id': f"{season}16{team7_id}{team8_id}_toilet",
                        'home_team': {
                            'id': team7_id,
                            'name': team7_data['team_name'],
                            'points': 88.0  # Simulated score
                        },
                        'away_team': {
                            'id': team8_id,
                            'name': team8_data['team_name'],
                            'points': 85.0  # Simulated score
                        },
                        'winner': team7_id,  # Seed 7 wins (7th place)
                        'note': 'Toilet bowl winners bracket: Seed 7 wins = 7th place'
                    }
                    brackets['consolation_bracket']['toilet_bowl'].append(week16_winners_game)
        
        # Add seeding information
        brackets['seeds'] = {
            'winners_bracket': [
                {'seed': i+1, 'team_id': team_id, 'team_name': data['team_name'], 'record': f"{data['wins']}-{data['losses']}-{data['ties']}"}
                for i, (team_id, data) in enumerate(winners_teams)
            ]
        }
        
        # Handle different seeding structures based on season
        if season == 2017:
            # 2017: 10-team format with divisions - winners bracket: 1-4, mediocre bowl: 5-6, toilet bowl: 7-10
            # Exclude mediocre bowl teams from consolation bracket
            toilet_bowl_teams = [team for team in consolation_teams if team[0] not in {team['team_id'] for team in brackets.get('middle_teams', [])}]
            brackets['seeds']['consolation_bracket'] = [
                {'seed': i+7, 'team_id': team_id, 'team_name': data['team_name'], 'record': f"{data['wins']}-{data['losses']}-{data['ties']}"}
                for i, (team_id, data) in enumerate(toilet_bowl_teams)
            ]
        elif season >= 2018:
            # 2018+: 12-team format - winners bracket: 1-6, mediocre bowl: 7-8, toilet bowl: 9-12
            # Use the middle_teams and consolation_teams from _get_playoff_teams
            if middle_teams:
                # Add middle teams section (seeds 7-8)
                brackets['middle_teams'] = [
                    {'seed': i+7, 'team_id': team_id, 'team_name': data['team_name'], 'record': f"{data['wins']}-{data['losses']}-{data['ties']}"}
                    for i, (team_id, data) in enumerate(middle_teams)
                ]
                
                # Add consolation bracket (toilet bowl teams only, seeds 9-12)
                brackets['seeds']['consolation_bracket'] = [
                    {'seed': i+9, 'team_id': team_id, 'team_name': data['team_name'], 'record': f"{data['wins']}-{data['losses']}-{data['ties']}"}
                    for i, (team_id, data) in enumerate(consolation_teams)
                ]
            else:
                # Fallback if not enough teams
                brackets['seeds']['consolation_bracket'] = [
                    {'seed': i+config.winners_bracket_size+1, 'team_id': team_id, 'team_name': data['team_name'], 'record': f"{data['wins']}-{data['losses']}-{data['ties']}"}
                    for i, (team_id, data) in enumerate(consolation_teams)
                ]
        else:
            # Default for other seasons
            brackets['seeds']['consolation_bracket'] = [
                {'seed': i+config.winners_bracket_size+1, 'team_id': team_id, 'team_name': data['team_name'], 'record': f"{data['wins']}-{data['losses']}-{data['ties']}"}
                for i, (team_id, data) in enumerate(consolation_teams)
            ]
        
        # Add first round matchups based on configuration
        brackets['first_round_matchups'] = config.first_round_matchups
        
        return brackets
        
    def save_playoff_brackets(self, season: int) -> None:
        """
        Generate and save playoff brackets to a JSON file.
        
        Args:
            season: The NFL season year
        """
        brackets = self.generate_playoff_brackets(season)
        
        # Save to JSON file
        output_path = self.processed_dir / f"{season}" / "playoff_brackets.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(brackets, f, indent=2)
            
        print(f"✓ Saved playoff brackets to {output_path}")

    def _calculate_two_week_bowl_results(self, season: int) -> Dict:
        """
        Calculate two-week cumulative results for mediocre bowl and toilet bowl matchups.
        
        Args:
            season: The NFL season year
            
        Returns:
            Dict containing cumulative results for mediocre bowl and toilet bowl
        """
        # Load the playoff brackets to get the correct team assignments
        brackets_path = self._get_processed_path(season).parent / 'playoff_brackets.json'
        if not brackets_path.exists():
            raise FileNotFoundError(f"No playoff brackets found for season {season}")
        with open(brackets_path, 'r') as f:
            brackets = json.load(f)
        
        # Get team IDs for each bracket
        middle_team_ids = {team['team_id'] for team in brackets.get('middle_teams', [])}
        consolation_team_ids = {team['team_id'] for team in brackets.get('seeds', {}).get('consolation_bracket', [])}
        
        print(f"DEBUG: Middle team IDs: {middle_team_ids}")
        print(f"DEBUG: Consolation team IDs: {consolation_team_ids}")
        
        # Load the annotated schedule data (with playoff_round values)
        annotated_schedule_path = self._get_processed_path(season).parent / 'schedule_annotated.csv'
        if not annotated_schedule_path.exists():
            raise FileNotFoundError(f"No annotated schedule found for season {season}")
        with open(annotated_schedule_path, 'r') as f:
            reader = csv.DictReader(f)
            games = list(reader)
        
        # Filter for Week 15 and 16 games
        week_15_games = [g for g in games if int(g['week']) == 15]
        week_16_games = [g for g in games if int(g['week']) == 16]
        
        print(f"DEBUG: Week 15 games: {len(week_15_games)}")
        for game in week_15_games:
            print(f"  {game['home_team']} ({game['home_team_id']}) vs {game['away_team']} ({game['away_team_id']}) - {game.get('playoff_round', 'N/A')}")
        
        print(f"DEBUG: Week 16 games: {len(week_16_games)}")
        for game in week_16_games:
            print(f"  {game['home_team']} ({game['home_team_id']}) vs {game['away_team']} ({game['away_team_id']}) - {game.get('playoff_round', 'N/A')}")
        
        # Initialize team scores for two-week bowls (cumulative across both weeks)
        mediocre_team_scores = {team_id: {'week_15': 0.0, 'week_16': 0.0, 'total': 0.0, 'team_name': ''} for team_id in middle_team_ids}
        toilet_team_scores = {team_id: {'week_15': 0.0, 'week_16': 0.0, 'total': 0.0, 'team_name': ''} for team_id in consolation_team_ids}
        
        # Get team names from brackets
        for team in brackets.get('seeds', {}).get('consolation_bracket', []):
            team_id = team['team_id']
            if team_id in toilet_team_scores:
                toilet_team_scores[team_id]['team_name'] = team['team_name']
        
        for team in brackets.get('middle_teams', []):
            team_id = team['team_id']
            if team_id in mediocre_team_scores:
                mediocre_team_scores[team_id]['team_name'] = team['team_name']
        
        # Process actual games for mediocre bowl (middle teams)
        for game in week_15_games:
            home_id = game['home_team_id']
            away_id = game['away_team_id']
            
            if home_id in middle_team_ids and away_id in middle_team_ids:
                # This is a mediocre bowl game
                home_points = float(game['home_points'])
                away_points = float(game['away_points'])
                
                mediocre_team_scores[home_id]['week_15'] = home_points
                mediocre_team_scores[away_id]['week_15'] = away_points
                mediocre_team_scores[home_id]['total'] += home_points
                mediocre_team_scores[away_id]['total'] += away_points
        
        for game in week_16_games:
            home_id = game['home_team_id']
            away_id = game['away_team_id']
            
            if home_id in middle_team_ids and away_id in middle_team_ids:
                # This is a mediocre bowl game
                home_points = float(game['home_points'])
                away_points = float(game['away_points'])
                
                mediocre_team_scores[home_id]['week_16'] = home_points
                mediocre_team_scores[away_id]['week_16'] = away_points
                mediocre_team_scores[home_id]['total'] += home_points
                mediocre_team_scores[away_id]['total'] += away_points
        
        # Process simulated toilet bowl games from brackets
        toilet_bracket = brackets.get('consolation_bracket', {})
        
        # Week 15 toilet bowl games (from round_1 if they have _toilet suffix)
        for game in toilet_bracket.get('round_1', []):
            if '_toilet' in game.get('game_id', ''):
                home_id = game['home_team']['id']
                away_id = game['away_team']['id']
                
                if home_id in toilet_team_scores and away_id in toilet_team_scores:
                    home_points = float(game['home_team']['points'])
                    away_points = float(game['away_team']['points'])
                    
                    toilet_team_scores[home_id]['week_15'] = home_points
                    toilet_team_scores[away_id]['week_15'] = away_points
                    toilet_team_scores[home_id]['total'] += home_points
                    toilet_team_scores[away_id]['total'] += away_points
        
        # Week 16 toilet bowl games (all games in toilet_bowl round are toilet bowl games)
        for game in toilet_bracket.get('toilet_bowl', []):
            home_id = game['home_team']['id']
            away_id = game['away_team']['id']
            
            if home_id in toilet_team_scores and away_id in toilet_team_scores:
                home_points = float(game['home_team']['points'])
                away_points = float(game['away_team']['points'])
                
                toilet_team_scores[home_id]['week_16'] = home_points
                toilet_team_scores[away_id]['week_16'] = away_points
                toilet_team_scores[home_id]['total'] += home_points
                toilet_team_scores[away_id]['total'] += away_points
        
        print(f"DEBUG: Mediocre team scores: {mediocre_team_scores}")
        print(f"DEBUG: Toilet team scores: {toilet_team_scores}")
        
        return {
            'mediocre_bowl': mediocre_team_scores,
            'toilet_bowl': toilet_team_scores
        }

    def _extract_championship_team_week_points(self, brackets: dict, team_id: str) -> tuple:
        """
        Extract individual week points for a championship bracket team.
        
        Args:
            brackets: The playoff brackets data
            team_id: The team ID to extract points for
            
        Returns:
            Tuple of (week_15_points, week_16_points)
        """
        week_15_points = 0.0
        week_16_points = 0.0
        
        # Extract Week 15 points from round_1
        for game in brackets['winners_bracket']['round_1']:
            if game['home_team']['id'] == team_id:
                week_15_points = game['home_team']['points']
                break
            elif game['away_team']['id'] == team_id:
                week_15_points = game['away_team']['points']
                break
        
        # Extract Week 16 points from championship_week
        for game_type in ['championship', 'third_place']:
            for game in brackets['winners_bracket']['championship_week'].get(game_type, []):
                if game['home_team']['id'] == team_id:
                    week_16_points = game['home_team']['points']
                    break
                elif game['away_team']['id'] == team_id:
                    week_16_points = game['away_team']['points']
                    break
            if week_16_points > 0:
                break
        
        return week_15_points, week_16_points

    def generate_postseason_standings(self, season: int) -> list:
        """
        Generate final postseason standings based on playoff results.
        
        Args:
            season: The NFL season year
            
        Returns:
            List of dictionaries containing team standings with both numeric place and label
        """
        # Get playoff configuration for the season
        config = PlayoffConfig.get_config(season)
        
        # Load the playoff brackets
        brackets_path = self._get_processed_path(season).parent / 'playoff_brackets.json'
        if not brackets_path.exists():
            raise FileNotFoundError(f"No playoff brackets found for season {season}")
        with open(brackets_path, 'r') as f:
            brackets = json.load(f)
            
        # Determine number of teams from schedule
        schedule_path = self._get_processed_path(season)
        with open(schedule_path, 'r') as f:
            reader = csv.DictReader(f)
            teams = set()
            for row in reader:
                teams.add(row['home_team_id'])
                teams.add(row['away_team_id'])
        num_teams = len(teams)
        
        # Initialize standings
        standings = []
        assigned_team_ids = set()
        
        print(f"=== DEBUG: Generating postseason standings for {season} ===")
        print(f"Total teams in league: {num_teams}")
        
        # Process winners bracket results
        winners_bracket = brackets['winners_bracket']
        
        print(f"=== DEBUG: Championship bracket games ===")
        print(f"Championship games: {len(winners_bracket['championship_week']['championship'])}")
        print(f"Third place games: {len(winners_bracket['championship_week']['third_place'])}")
        print(f"Round 1 games: {len(winners_bracket['round_1'])}")
        
        # Championship game winner is 1st place
        if winners_bracket['championship_week']['championship']:
            champ_game = winners_bracket['championship_week']['championship'][0]
            winner_id = champ_game['winner']
            winner = champ_game['home_team'] if winner_id == champ_game['home_team']['id'] else champ_game['away_team']
            week_15_points, week_16_points = self._extract_championship_team_week_points(brackets, winner_id)
            print(f"DEBUG: 1st Place - {winner['name']} (Team {winner_id})")
            standings.append({
                'place': 1,
                'label': config.place_names['champion'],
                'team_id': winner_id,
                'team_name': winner['name'],
                'points': week_15_points + week_16_points,
                'week_15_points': week_15_points,
                'week_16_points': week_16_points
            })
            assigned_team_ids.add(winner_id)
            
        # Championship game loser is 2nd place
        if winners_bracket['championship_week']['championship']:
            champ_game = winners_bracket['championship_week']['championship'][0]
            loser_id = champ_game['home_team']['id'] if champ_game['winner'] == champ_game['away_team']['id'] else champ_game['away_team']['id']
            loser = champ_game['home_team'] if loser_id == champ_game['home_team']['id'] else champ_game['away_team']
            week_15_points, week_16_points = self._extract_championship_team_week_points(brackets, loser_id)
            print(f"DEBUG: 2nd Place - {loser['name']} (Team {loser_id})")
            standings.append({
                'place': 2,
                'label': config.place_names['runner_up'],
                'team_id': loser_id,
                'team_name': loser['name'],
                'points': week_15_points + week_16_points,
                'week_15_points': week_15_points,
                'week_16_points': week_16_points
            })
            assigned_team_ids.add(loser_id)
            
        # Third place game winner is 3rd place
        if winners_bracket['championship_week']['third_place']:
            # Process all third place games to find the actual third place winner
            third_place_games = winners_bracket['championship_week']['third_place']
            third_place_winners = []
            third_place_losers = []
            
            for third_game in third_place_games:
                winner_id = third_game['winner']
                loser_id = third_game['home_team']['id'] if third_game['winner'] == third_game['away_team']['id'] else third_game['away_team']['id']
                
                if winner_id not in assigned_team_ids:
                    third_place_winners.append((winner_id, third_game))
                if loser_id not in assigned_team_ids:
                    third_place_losers.append((loser_id, third_game))
            
            # Assign third place to the first unassigned winner
            if third_place_winners:
                winner_id, third_game = third_place_winners[0]
                winner = third_game['home_team'] if winner_id == third_game['home_team']['id'] else third_game['away_team']
                week_15_points, week_16_points = self._extract_championship_team_week_points(brackets, winner_id)
                standings.append({
                    'place': 3,
                    'label': config.place_names['third_place'],
                    'team_id': winner_id,
                    'team_name': winner['name'],
                    'points': week_15_points + week_16_points,
                    'week_15_points': week_15_points,
                    'week_16_points': week_16_points
                })
                assigned_team_ids.add(winner_id)
            
        # Third place game loser is 4th place
        if winners_bracket['championship_week']['third_place']:
            # Process all third place games to find the actual third place loser
            third_place_games = winners_bracket['championship_week']['third_place']
            third_place_losers = []
            
            for third_game in third_place_games:
                loser_id = third_game['home_team']['id'] if third_game['winner'] == third_game['away_team']['id'] else third_game['away_team']['id']
                if loser_id not in assigned_team_ids:
                    third_place_losers.append((loser_id, third_game))
            
            # Assign fourth place to the first unassigned loser
            if third_place_losers:
                loser_id, third_game = third_place_losers[0]
                loser = third_game['home_team'] if loser_id == third_game['home_team']['id'] else third_game['away_team']
                week_15_points, week_16_points = self._extract_championship_team_week_points(brackets, loser_id)
                standings.append({
                    'place': 4,
                    'label': config.place_names['fourth_place'],
                    'team_id': loser_id,
                    'team_name': loser['name'],
                    'points': week_15_points + week_16_points,
                    'week_15_points': week_15_points,
                    'week_16_points': week_16_points
                })
                assigned_team_ids.add(loser_id)
            
        # Handle teams that lost in the first round of the championship bracket (places 5-6)
        if winners_bracket['round_1']:
            first_round_losers = []
            print(f"=== DEBUG: Processing first round losers ===")
            for game in winners_bracket['round_1']:
                loser_id = game['home_team']['id'] if game['winner'] == game['away_team']['id'] else game['away_team']['id']
                loser = game['home_team'] if loser_id == game['home_team']['id'] else game['away_team']
                print(f"DEBUG: First round loser - {loser['name']} (Team {loser_id})")
                if loser_id not in assigned_team_ids:
                    first_round_losers.append((loser_id, loser))
                    print(f"DEBUG: Added to first_round_losers list")
                else:
                    print(f"DEBUG: Already assigned, skipping")
            
            print(f"DEBUG: Total first round losers to assign: {len(first_round_losers)}")
            # Assign places 5-6 to first round losers
            for i, (loser_id, loser) in enumerate(first_round_losers):
                if i >= 2:  # Only assign up to 2 teams (places 5-6)
                    break
                place = 5 + i
                print(f"DEBUG: Assigning {place}th place to {loser['name']} (Team {loser_id})")
                week_15_points, week_16_points = self._extract_championship_team_week_points(brackets, loser_id)
                standings.append({
                    'place': place,
                    'label': config.place_names.get(f"{place}th_place", f"{place}th Place"),
                    'team_id': loser_id,
                    'team_name': loser['name'],
                    'points': week_15_points + week_16_points,
                    'week_15_points': week_15_points,
                    'week_16_points': week_16_points
                })
                assigned_team_ids.add(loser_id)

        elif season < 2018 and 'middle_teams' in brackets:
            # Calculate two-week bowl results
            bowl_results = self._calculate_two_week_bowl_results(season)
            
            # Process mediocre bowl results (teams 5-8)
            mediocre_teams = []
            for team_id, team_data in bowl_results['mediocre_bowl'].items():
                mediocre_teams.append({
                    'id': team_id,
                    'name': team_data['team_name'],
                    'total_points': team_data['total'],
                    'week_15': team_data['week_15'],
                    'week_16': team_data['week_16']
                })
            
            # Sort mediocre teams by total points (highest first)
            mediocre_teams.sort(key=lambda x: x['total_points'], reverse=True)
            
            # Assign places 5-8 based on mediocre bowl results
            for i, team in enumerate(mediocre_teams):
                if team['id'] in assigned_team_ids:
                    continue
                place = 5 + i
                if place > 8:
                    break
                standings.append({
                    'place': place,
                    'label': config.place_names.get(f"{place}th_place", f"{place}th Place"),
                    'team_id': team['id'],
                    'team_name': team['name'],
                    'points': team['total_points'],
                    'week_15_points': team['week_15'],
                    'week_16_points': team['week_16']
                })
                assigned_team_ids.add(team['id'])
            
            # Process toilet bowl results (teams 9-12)
            toilet_teams = []
            for team_id, team_data in bowl_results['toilet_bowl'].items():
                toilet_teams.append({
                    'id': team_id,
                    'name': team_data['team_name'],
                    'total_points': team_data['total'],
                    'week_15': team_data['week_15'],
                    'week_16': team_data['week_16']
                })
            
            # Sort toilet teams by total points (highest first)
            toilet_teams.sort(key=lambda x: x['total_points'], reverse=True)
            
            # Assign places 9-12 based on toilet bowl results
            for i, team in enumerate(toilet_teams):
                if team['id'] in assigned_team_ids:
                    continue
                place = 9 + i
                if place > 12:
                    break
                standings.append({
                    'place': place,
                    'label': config.place_names.get(f"{place}th_place", f"{place}th Place"),
                    'team_id': team['id'],
                    'team_name': team['name'],
                    'points': team['total_points'],
                    'week_15_points': team['week_15'],
                    'week_16_points': team['week_16']
                })
                assigned_team_ids.add(team['id'])
        else:
            # 2018+ format: Process consolation bracket (seeds 7-12)
            # Use regular season standings to determine mediocre bowl teams (7th and 8th place)
            # instead of relying on playoff bracket seeds which may be incorrect
            
            # Get regular season standings to identify the correct mediocre bowl teams
            regular_standings = self.generate_regular_season_standings(season)
            mediocre_bowl_team_ids = {regular_standings[6]['team_id'], regular_standings[7]['team_id']}  # 7th and 8th place
            
            mediocre_bowl_teams = []
            toilet_bowl_teams = []
            
            for seed in brackets['seeds']['consolation_bracket']:
                team_info = {
                    'id': seed['team_id'],
                    'name': seed['team_name'],
                    'seed': seed['seed'],
                    'points': 0.0  # Initialize points
                }
                
                if team_info['id'] in mediocre_bowl_team_ids:  # Use regular season standings
                    mediocre_bowl_teams.append(team_info)
                else:  # All other consolation teams are toilet bowl
                    toilet_bowl_teams.append(team_info)
            
            # Update points for mediocre bowl teams from their actual games
            # For 2018+, mediocre bowl teams play each other in weeks 14-16
            mediocre_bowl_results = self._calculate_mediocre_bowl_results_2018_plus(season)
            for team in mediocre_bowl_teams:
                if team['id'] in mediocre_bowl_results:
                    team['points'] = mediocre_bowl_results[team['id']]['total_points']
                    team['week_14_points'] = mediocre_bowl_results[team['id']].get('week_14_points', 0.0)
                    team['week_15_points'] = mediocre_bowl_results[team['id']]['week_15_points']
                    team['week_16_points'] = mediocre_bowl_results[team['id']]['week_16_points']
            
            # Update points for toilet bowl teams from their actual games
            for game in brackets['consolation_bracket']['toilet_bowl']:
                for team in toilet_bowl_teams:
                    if team['id'] == game['home_team']['id']:
                        team['points'] += game['home_team']['points']
                    elif team['id'] == game['away_team']['id']:
                        team['points'] += game['away_team']['points']
            
            # Sort mediocre bowl teams by total points (highest first)
            mediocre_bowl_teams.sort(key=lambda x: x['points'], reverse=True)
            
            # Assign places 7-8 based on mediocre bowl results
            for i, team in enumerate(mediocre_bowl_teams):
                if team['id'] in assigned_team_ids:
                    continue
                place = 7 + i
                if place > 8:
                    break
                label = config.place_names.get(f"{place}th_place", f"{place}th Place")
                standings.append({
                    'place': place,
                    'label': label,
                    'team_id': team['id'],
                    'team_name': team['name'],
                    'points': team['points'],
                    'week_14_points': team.get('week_14_points', 0.0),
                    'week_15_points': team.get('week_15_points', 0.0),
                    'week_16_points': team.get('week_16_points', 0.0)
                })
                assigned_team_ids.add(team['id'])
            
            # Sort toilet bowl teams by total points (highest first)
            toilet_bowl_teams.sort(key=lambda x: x['points'], reverse=True)
            
            # Assign places 9-12 based on toilet bowl results
            for i, team in enumerate(toilet_bowl_teams):
                if team['id'] in assigned_team_ids:
                    continue
                place = 9 + i
                if place > 12:
                    break
                label = config.place_names.get(f"{place}th_place", f"{place}th Place")
                standings.append({
                    'place': place,
                    'label': label,
                    'team_id': team['id'],
                    'team_name': team['name'],
                    'points': team['points'],
                    'week_15_points': 0.0,  # Toilet bowl teams don't have individual week breakdowns
                    'week_16_points': 0.0
                })
                assigned_team_ids.add(team['id'])
        
        # Sort standings by place
        standings.sort(key=lambda x: x['place'])
        
        print(f"=== DEBUG: Final postseason standings ===")
        for team in standings:
            print(f"Place {team['place']}: {team['team_name']} (Team {team['team_id']}) - {team['label']}")
        
        print(f"=== DEBUG: Assigned team IDs ===")
        print(f"Assigned: {sorted(assigned_team_ids)}")
        
        # Ensure all 12 places are filled (no duplicates)
        # Collect all seeded teams from brackets
        all_seeded_teams = []
        for bracket in ['winners_bracket', 'consolation_bracket']:
            for seed in brackets['seeds'].get(bracket, []):
                all_seeded_teams.append({
                    'team_id': seed['team_id'],
                    'team_name': seed['team_name'],
                    'seed': seed['seed']
                })
        if season < 2018 and 'middle_teams' in brackets:
            for team in brackets['middle_teams']:
                all_seeded_teams.append({
                    'team_id': team['team_id'],
                    'team_name': team['team_name'],
                    'seed': team['seed']
                })
        # Find unassigned teams
        placed_ids = set(s['team_id'] for s in standings)
        unplaced = [t for t in all_seeded_teams if t['team_id'] not in placed_ids]
        print(f"=== DEBUG: Unassigned teams ===")
        for team in unplaced:
            print(f"Unassigned: {team['team_name']} (Team {team['team_id']}, Seed {team['seed']})")
        # Assign to next available places
        next_place = max([s['place'] for s in standings], default=0) + 1
        for team in sorted(unplaced, key=lambda x: x['seed']):
            if next_place > num_teams:
                break
            print(f"DEBUG: Auto-assigning {next_place}th place to {team['team_name']} (Team {team['team_id']})")
            standings.append({
                'place': next_place,
                'label': config.place_names.get(f"{next_place}th_place", f"{next_place}th Place"),
                'team_id': team['team_id'],
                'team_name': team['team_name'],
                'points': 0.0
            })
            next_place += 1
        standings.sort(key=lambda x: x['place'])
        
        # Patch: Ensure 'points' is always the sum of week_15_points and week_16_points
        for team in standings:
            week_15 = team.get('week_15_points', 0.0)
            week_16 = team.get('week_16_points', 0.0)
            team['points'] = week_15 + week_16
        
        # In generate_postseason_standings, update 5th/6th place assignment for 2018+ to use the fifth_place game result
        # Handle teams that lost in the first round of the championship bracket (places 5-6)
        if season >= 2018 and winners_bracket['championship_week'].get('fifth_place'):
            fifth_place_games = winners_bracket['championship_week']['fifth_place']
            if fifth_place_games:
                game = fifth_place_games[0]
                winner_id = game['winner']
                loser_id = game['home_team']['id'] if game['winner'] == game['away_team']['id'] else game['away_team']['id']
                # 5th place
                winner = game['home_team'] if winner_id == game['home_team']['id'] else game['away_team']
                standings.append({
                    'place': 5,
                    'label': config.place_names.get('fifth_place', 'Fifth Place'),
                    'team_id': winner_id,
                    'team_name': winner['name'],
                    'points': game['home_team']['points'] if winner_id == game['home_team']['id'] else game['away_team']['points'],
                    'week_16_points': game['home_team']['points'] if winner_id == game['home_team']['id'] else game['away_team']['points'],
                    'week_15_points': 0.0
                })
                assigned_team_ids.add(winner_id)
                # 6th place
                loser = game['home_team'] if loser_id == game['home_team']['id'] else game['away_team']
                standings.append({
                    'place': 6,
                    'label': config.place_names.get('sixth_place', 'Sixth Place'),
                    'team_id': loser_id,
                    'team_name': loser['name'],
                    'points': game['home_team']['points'] if loser_id == game['home_team']['id'] else game['away_team']['points'],
                    'week_16_points': game['home_team']['points'] if loser_id == game['home_team']['id'] else game['away_team']['points'],
                    'week_15_points': 0.0
                })
                assigned_team_ids.add(loser_id)

        # Handle toilet bowl teams (places 9-12) for 2018+ seasons
        if season >= 2018:
            # Load schedule to find toilet bowl championship and 3rd place games
            schedule_path = self._get_processed_path(season)
            if schedule_path.exists():
                with open(schedule_path, 'r') as f:
                    reader = csv.DictReader(f)
                    games = list(reader)
                
                # Find toilet bowl championship and 3rd place games from week 16
                toilet_championship_game = None
                toilet_third_place_game = None
                
                for game in games:
                    if (game['week'] == '16' and 
                        game.get('simulation_type') == 'toilet_bowl_championship'):
                        toilet_championship_game = game
                    elif (game['week'] == '16' and 
                          game.get('simulation_type') == 'toilet_bowl_third_place'):
                        toilet_third_place_game = game
                
                # Assign 9th and 10th place based on championship game
                if toilet_championship_game:
                    home_points = float(toilet_championship_game['home_points'])
                    away_points = float(toilet_championship_game['away_points'])
                    
                    if home_points > away_points:
                        # Home team wins championship (9th place)
                        champ_winner_id = toilet_championship_game['home_team_id']
                        champ_winner_name = toilet_championship_game['home_team']
                        champ_winner_points = home_points
                        champ_loser_id = toilet_championship_game['away_team_id']
                        champ_loser_name = toilet_championship_game['away_team']
                        champ_loser_points = away_points
                    else:
                        # Away team wins championship (9th place)
                        champ_winner_id = toilet_championship_game['away_team_id']
                        champ_winner_name = toilet_championship_game['away_team']
                        champ_winner_points = away_points
                        champ_loser_id = toilet_championship_game['home_team_id']
                        champ_loser_name = toilet_championship_game['home_team']
                        champ_loser_points = home_points
                    
                    # 9th place (Toilet Bowl Champion)
                    standings.append({
                        'place': 9,
                        'label': config.place_names.get('ninth_place', 'Ninth Place'),
                        'team_id': champ_winner_id,
                        'team_name': champ_winner_name,
                        'points': champ_winner_points,
                        'week_16_points': champ_winner_points,
                        'week_15_points': 0.0
                    })
                    assigned_team_ids.add(champ_winner_id)
                    
                    # 10th place (Toilet Bowl Runner Up)
                    standings.append({
                        'place': 10,
                        'label': config.place_names.get('tenth_place', 'Tenth Place'),
                        'team_id': champ_loser_id,
                        'team_name': champ_loser_name,
                        'points': champ_loser_points,
                        'week_16_points': champ_loser_points,
                        'week_15_points': 0.0
                    })
                    assigned_team_ids.add(champ_loser_id)
                
                # Assign 11th and 12th place based on 3rd place game
                if toilet_third_place_game:
                    home_points = float(toilet_third_place_game['home_points'])
                    away_points = float(toilet_third_place_game['away_points'])
                    
                    if home_points > away_points:
                        # Home team wins 3rd place game (11th place)
                        third_winner_id = toilet_third_place_game['home_team_id']
                        third_winner_name = toilet_third_place_game['home_team']
                        third_winner_points = home_points
                        third_loser_id = toilet_third_place_game['away_team_id']
                        third_loser_name = toilet_third_place_game['away_team']
                        third_loser_points = away_points
                    else:
                        # Away team wins 3rd place game (11th place)
                        third_winner_id = toilet_third_place_game['away_team_id']
                        third_winner_name = toilet_third_place_game['away_team']
                        third_winner_points = away_points
                        third_loser_id = toilet_third_place_game['home_team_id']
                        third_loser_name = toilet_third_place_game['home_team']
                        third_loser_points = home_points
                    
                    # 11th place (Toilet Bowl 3rd Place)
                    standings.append({
                        'place': 11,
                        'label': config.place_names.get('eleventh_place', 'Eleventh Place'),
                        'team_id': third_winner_id,
                        'team_name': third_winner_name,
                        'points': third_winner_points,
                        'week_16_points': third_winner_points,
                        'week_15_points': 0.0
                    })
                    assigned_team_ids.add(third_winner_id)
                    
                    # 12th place (Toilet Bowl 4th Place)
                    standings.append({
                        'place': 12,
                        'label': config.place_names.get('twelfth_place', 'Twelfth Place'),
                        'team_id': third_loser_id,
                        'team_name': third_loser_name,
                        'points': third_loser_points,
                        'week_16_points': third_loser_points,
                        'week_15_points': 0.0
                    })
                    assigned_team_ids.add(third_loser_id)

        # Return the final standings
        return standings

    def save_postseason_standings(self, season: int) -> None:
        """
        Generate and save final postseason standings to a JSON file (hybrid format).
        
        Args:
            season: The NFL season year
        """
        standings = self.generate_postseason_standings(season)
        # Save to JSON file
        output_path = self.processed_dir / f"{season}" / "postseason_standings.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(standings, f, indent=2)
        print(f"✓ Saved postseason standings to {output_path}")

    def generate_regular_season_standings(self, season: int) -> list:
        """
        Generate regular season standings based on game results.
        
        Args:
            season: The NFL season year
            
        Returns:
            List of dictionaries containing team standings
        """
        # Get playoff configuration for the season
        config = PlayoffConfig.get_config(season)
        
        # Load the schedule data
        schedule_path = self._get_processed_path(season)
        if not schedule_path.exists():
            raise FileNotFoundError(f"No schedule data found for season {season}")
            
        # Read the CSV
        games = []
        with open(schedule_path, 'r') as f:
            reader = csv.DictReader(f)
            games = list(reader)
            
        # Get regular season games (weeks 1-14)
        regular_season_games = [g for g in games if int(g['week']) <= config.regular_season_weeks]
        
        # Calculate team records
        team_records = {}
        
        for game in regular_season_games:
            home_id = game['home_team_id']
            away_id = game['away_team_id']
            home_points = float(game['home_points'])
            away_points = float(game['away_points'])
            
            # Initialize records if needed
            if home_id not in team_records:
                team_records[home_id] = {
                    'team_id': home_id,
                    'team_name': game['home_team'],
                    'wins': 0, 'losses': 0, 'ties': 0,
                    'points_for': 0.0, 'points_against': 0.0
                }
            if away_id not in team_records:
                team_records[away_id] = {
                    'team_id': away_id,
                    'team_name': game['away_team'],
                    'wins': 0, 'losses': 0, 'ties': 0,
                    'points_for': 0.0, 'points_against': 0.0
                }
                
            # Update records based on game results
            if home_points > away_points:
                team_records[home_id]['wins'] += 1
                team_records[away_id]['losses'] += 1
            elif home_points < away_points:
                team_records[home_id]['losses'] += 1
                team_records[away_id]['wins'] += 1
            else:
                team_records[home_id]['ties'] += 1
                team_records[away_id]['ties'] += 1
            
            # Update points
            team_records[home_id]['points_for'] += home_points
            team_records[home_id]['points_against'] += away_points
            team_records[away_id]['points_for'] += away_points
            team_records[away_id]['points_against'] += home_points
        
        # Convert to list and sort by win percentage, then points for (same logic as playoff team selection)
        standings = list(team_records.values())
        for team in standings:
            team['win_pct'] = (team['wins'] + 0.5 * team['ties']) / (team['wins'] + team['losses'] + team['ties'])
        
        standings.sort(key=lambda x: (x['win_pct'], x['points_for']), reverse=True)
        
        # Add place and record string
        for i, team in enumerate(standings, 1):
            team['place'] = i
            team['record'] = f"{team['wins']}-{team['losses']}-{team['ties']}"
            team['win_pct'] = (team['wins'] + 0.5 * team['ties']) / (team['wins'] + team['losses'] + team['ties'])
        
        return standings
    
    def save_regular_season_standings(self, season: int) -> None:
        """
        Generate and save regular season standings to a JSON file.
        
        Args:
            season: The NFL season year
        """
        standings = self.generate_regular_season_standings(season)
        # Save to JSON file
        output_path = self.processed_dir / f"{season}" / "regular_season_standings.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(standings, f, indent=2)
        print(f"✓ Saved regular season standings to {output_path}")
    
    def generate_final_standings(self, season: int) -> list:
        """
        Generate final combined standings (regular season + postseason).
        Final placement is based on regular season standings, with postseason results recorded separately.
        
        Args:
            season: The NFL season year
            
        Returns:
            List of dictionaries containing final standings
        """
        # Get regular season standings
        regular_standings = self.generate_regular_season_standings(season)
        
        # Get postseason standings
        postseason_standings = self.generate_postseason_standings(season)
        
        # Create final standings based on regular season results
        final_standings = []
        
        # For 2018+ seasons, explicitly assign mediocre bowl teams based on regular season standings
        mediocre_bowl_team_ids = set()
        if season >= 2018:
            # 7th and 8th place teams from regular season
            if len(regular_standings) >= 8:
                mediocre_bowl_team_ids = {regular_standings[6]['team_id'], regular_standings[7]['team_id']}
            # Load mediocre bowl totals
            mediocre_bowl_totals = {}
            mediocre_bowl_path = self.processed_dir / f"{season}" / "mediocre_bowl_standings.json"
            if mediocre_bowl_path.exists():
                with open(mediocre_bowl_path, 'r') as f:
                    mediocre_data = json.load(f)
                for mb_team in mediocre_data:
                    mediocre_bowl_totals[mb_team['team_id']] = mb_team['total_points']

        # Start with regular season standings as the base
        for reg_team in regular_standings:
            team_id = reg_team['team_id']
            # Find corresponding postseason data
            post_data = None
            for post_team in postseason_standings:
                if post_team['team_id'] == team_id:
                    post_data = post_team
                    break
            # Create final team entry
            final_team = {
                'place': reg_team['place'],  # Final place based on regular season
                'team_id': team_id,
                'team_name': reg_team['team_name'],
                'regular_season_record': reg_team['record'],
                'regular_season_points_for': reg_team['points_for'],
                'regular_season_points_against': reg_team['points_against'],
                'regular_season_win_pct': reg_team['win_pct'],
                'postseason_rank': None,
                'postseason_label': None,
                'postseason_points': 0.0,
                'week_15_points': 0.0,
                'week_16_points': 0.0,
                'mediocre_bowl_total': 0.0,
                'playoff_participation': 'none'
            }
            # Add postseason data if available
            if post_data:
                final_team['postseason_rank'] = post_data['place']
                final_team['postseason_label'] = post_data['label']
                final_team['postseason_points'] = post_data['points']
                final_team['week_15_points'] = post_data.get('week_15_points', 0.0)
                final_team['week_16_points'] = post_data.get('week_16_points', 0.0)
            # Determine playoff participation type
            if post_data and post_data['place'] <= 6:
                final_team['playoff_participation'] = 'championship_bracket'
            elif season >= 2018 and team_id in mediocre_bowl_team_ids:
                final_team['playoff_participation'] = 'mediocre_bowl'
                final_team['mediocre_bowl_total'] = mediocre_bowl_totals.get(team_id, 0.0)
                # Assign 7th and 8th place labels for mediocre bowl teams
                if reg_team['place'] == 7:
                    final_team['postseason_rank'] = 7
                    final_team['postseason_label'] = 'Seventh Place'
                elif reg_team['place'] == 8:
                    final_team['postseason_rank'] = 8
                    final_team['postseason_label'] = 'Eighth Place'
            elif season < 2018 and post_data and post_data['place'] in [5, 6]:
                final_team['playoff_participation'] = 'mediocre_bowl'
                final_team['mediocre_bowl_total'] = post_data.get('week_15_points', 0.0) + post_data.get('week_16_points', 0.0)
            elif post_data and post_data['place'] >= 7:
                final_team['playoff_participation'] = 'toilet_bowl'
            final_standings.append(final_team)
        
        # Sort by regular season place (final placement based on regular season performance)
        final_standings.sort(key=lambda x: x['place'])
        
        return final_standings
    
    def save_final_standings(self, season: int) -> None:
        """
        Generate and save final combined standings to a JSON file.
        
        Args:
            season: The NFL season year
        """
        standings = self.generate_final_standings(season)
        # Save to JSON file
        output_path = self.processed_dir / f"{season}" / "final_standings.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(standings, f, indent=2)
        print(f"✓ Saved final standings to {output_path}")
    
    def generate_mediocre_bowl_standings(self, season: int) -> list:
        """
        Generate mediocre bowl standings for bragging rights.
        For 2011-2017: Shows two-week cumulative results for middle teams (seeds 5-8).
        For 2018+: Shows three-week cumulative results for seeds 7-8 using injected games.
        For 2017, shows toilet bowl results since there are no mediocre bowl games.
        
        Args:
            season: The NFL season year
            
        Returns:
            List of dictionaries containing mediocre bowl standings
        """
        # For 2018+, use the injected mediocre bowl games from schedule
        if season >= 2018:
            return self._generate_mediocre_bowl_standings_2018_plus(season)
        
        # For 2011-2017, use the old two-week bowl logic
        # Get two-week bowl results
        bowl_results = self._calculate_two_week_bowl_results(season)
        
        # Create mediocre bowl standings
        mediocre_standings = []
        
        # For 2017, use toilet bowl results since there are no mediocre bowl games
        if season == 2017:
            bowl_data = bowl_results['toilet_bowl']
        else:
            bowl_data = bowl_results['mediocre_bowl']
        
        for team_id, team_data in bowl_data.items():
            if team_data['total'] > 0:  # Only include teams that actually played
                mediocre_standings.append({
                    'team_id': team_id,
                    'team_name': team_data['team_name'],
                    'week_15_points': team_data['week_15'],
                    'week_16_points': team_data['week_16'],
                    'total_points': team_data['total'],
                    'week_15_opponent': None,  # Could be added if needed
                    'week_16_opponent': None   # Could be added if needed
                })
        
        # Sort by total points (highest first for mediocre bowl, lowest first for toilet bowl)
        if season == 2017:
            # For toilet bowl, lowest total wins (biggest loser)
            mediocre_standings.sort(key=lambda x: x['total_points'])
        else:
            # For mediocre bowl, highest total wins
            mediocre_standings.sort(key=lambda x: x['total_points'], reverse=True)
        
        # Add place
        for i, team in enumerate(mediocre_standings, 1):
            team['place'] = i
            if season == 2017:
                # Toilet bowl places (1st = biggest loser)
                team['label'] = f"{i}st Place" if i == 1 else f"{i}nd Place" if i == 2 else f"{i}rd Place" if i == 3 else f"{i}th Place"
            else:
                # Mediocre bowl places (1st = winner)
                team['label'] = f"{i}st Place" if i == 1 else f"{i}nd Place" if i == 2 else f"{i}rd Place" if i == 3 else f"{i}th Place"
        
        return mediocre_standings
    
    def _generate_mediocre_bowl_standings_2018_plus(self, season: int) -> list:
        """
        Generate mediocre bowl standings for 2018+ seasons based on regular season results for 7th and 8th place teams.
        
        Args:
            season: The NFL season year
            
        Returns:
            List of dictionaries containing mediocre bowl standings
        """
        # Load regular season standings to get 7th and 8th place teams
        standings_path = self.processed_dir / f"{season}" / "regular_season_standings.json"
        if not standings_path.exists():
            print(f"No regular season standings found for season {season}")
            return []
        
        import json
        with open(standings_path, 'r') as f:
            standings = json.load(f)
        
        if len(standings) < 8:
            print(f"Not enough teams in regular season standings for season {season}")
            return []
        
        # Get 7th and 8th place teams (mediocre bowl teams)
        mediocre_teams = standings[6:8]  # indices 6-7 (7th and 8th place)
        
        # Create mediocre bowl standings based on regular season performance
        mediocre_standings = []
        for i, team in enumerate(mediocre_teams, 1):
            mediocre_standings.append({
                'team_id': team['team_id'],
                'team_name': team['team_name'],
                'week_14_points': 0.0,  # No actual games, just regular season results
                'week_15_points': 0.0,
                'week_16_points': 0.0,
                'total_points': team['points_for'],  # Use regular season points for
                'place': i,
                'label': f"{i}st Place" if i == 1 else f"{i}nd Place" if i == 2 else f"{i}rd Place" if i == 3 else f"{i}th Place",
                'regular_season_record': team['record'],
                'regular_season_place': team['place']
            })
        
        # Sort by regular season points for (highest first)
        mediocre_standings.sort(key=lambda x: x['total_points'], reverse=True)
        
        # Update place and label after sorting
        for i, team in enumerate(mediocre_standings, 1):
            team['place'] = i
            team['label'] = f"{i}st Place" if i == 1 else f"{i}nd Place" if i == 2 else f"{i}rd Place" if i == 3 else f"{i}th Place"
        
        return mediocre_standings
    
    def save_mediocre_bowl_standings(self, season: int) -> None:
        """
        Generate and save mediocre bowl standings to a JSON file.
        
        Args:
            season: The NFL season year
        """
        standings = self.generate_mediocre_bowl_standings(season)
        # Save to JSON file
        output_path = self.processed_dir / f"{season}" / "mediocre_bowl_standings.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(standings, f, indent=2)
        print(f"✓ Saved mediocre bowl standings to {output_path}")
    
    def save_all_standings(self, season: int) -> None:
        """
        Generate and save all standings files for a season.
        
        Args:
            season: The NFL season year
        """
        print(f"Generating all standings for {season}...")
        
        # Generate regular season standings
        self.save_regular_season_standings(season)
        
        # Generate postseason standings
        self.save_postseason_standings(season)
        
        # Generate mediocre bowl standings (for bragging rights)
        self.save_mediocre_bowl_standings(season)
        
        # Generate final combined standings
        self.save_final_standings(season)
        
        print(f"✓ All standings generated for {season}")

    def inject_toilet_bowl_games(self, season: int) -> None:
        """
        Inject simulated toilet bowl games into the schedule CSV.
        For 2018+: Uses api_client_v2_optimized to get actual team scores including kicker and defense points.
        For 2011-2017: Uses placeholder scores from playoff bracket generation.
        This allows the games to be properly annotated and tracked.
        
        Args:
            season: The NFL season year
        """
        # For 2018+, use real scores from API client
        if season >= 2018:
            self._inject_toilet_bowl_games_with_real_scores(season)
        else:
            self._inject_toilet_bowl_games_with_placeholders(season)
    
    def _inject_toilet_bowl_games_with_real_scores(self, season: int) -> None:
        """
        Inject toilet bowl games with real scores for 2018+ seasons.
        Properly tracks bracket progression: Week 14 (first round), Week 15 (semifinals), Week 16 (championship and 3rd place).
        """
        # Load regular season standings to get seeds 9-12
        standings_path = self.processed_dir / f"{season}" / "regular_season_standings.json"
        if not standings_path.exists():
            print(f"No regular season standings found for season {season}")
            return
        
        import json
        with open(standings_path, 'r') as f:
            standings = json.load(f)
        
        if len(standings) < 12:
            print(f"Not enough teams in regular season standings for season {season}")
            return
        
        # Get seeds 9-12 (toilet bowl teams)
        toilet_teams = standings[8:12]  # indices 8-11 (seeds 9-12)
        
        # Load existing schedule
        schedule_path = self._get_processed_path(season)
        if not schedule_path.exists():
            print(f"No schedule found for season {season}")
            return
        
        import csv
        existing_games = []
        with open(schedule_path, 'r') as f:
            reader = csv.DictReader(f)
            existing_games = list(reader)
        
        # Use api_client_v2_optimized to get real scores
        try:
            from src.ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper
            api_client = NFLFantasyMultiTableScraper()
            league_id = self._get_league_id(str(season))
        except ImportError:
            print("api_client_v2_optimized not available, falling back to schedule data")
            api_client = None
        
        # Helper to get real score for a team in a week
        def get_real_score(team_id, week):
            if api_client:
                # Use optimized API client to get actual score with all player types
                try:
                    team_data = api_client.get_team_data(league_id, team_id, season, int(week), force_refresh=False)
                    if team_data and 'players' in team_data:
                        # Count only starters' points (exclude bench players)
                        starter_points = sum(
                            player.get('fantasy_points', 0.0) 
                            for player in team_data['players'] 
                            if player.get('lineup_status') == 'starter'
                        )
                        return starter_points
                except Exception as e:
                    print(f"Error getting score for team {team_id} week {week}: {e}")
            
            # Fallback to schedule data
            for g in existing_games:
                if g['week'] == week and (g['home_team_id'] == team_id or g['away_team_id'] == team_id):
                    return float(g['home_points']) if g['home_team_id'] == team_id else float(g['away_points'])
            return 0.0
        
        # Create toilet bowl games for weeks 14, 15, and 16
        toilet_games = []
        
        # Week 14: First round of toilet bowl (seeds 9 vs 12, 10 vs 11)
        week14_games = [
            (toilet_teams[0], toilet_teams[3]),  # 9 vs 12
            (toilet_teams[1], toilet_teams[2])   # 10 vs 11
        ]
        
        week14_winners = []
        week14_losers = []
        
        for i, (team1, team2) in enumerate(week14_games):
            team1_points = get_real_score(team1['team_id'], '14')
            team2_points = get_real_score(team2['team_id'], '14')
            
            toilet_games.append({
                'game_id': f"{season}14{team1['team_id']}{team2['team_id']}_toilet_round1",
                'season': season,
                'week': '14',
                'home_team': team1['team_name'],
                'home_team_id': team1['team_id'],
                'home_points': team1_points,
                'home_record': '0-0-0',
                'home_rank': 0,
                'away_team': team2['team_name'],
                'away_team_id': team2['team_id'],
                'away_points': team2_points,
                'away_record': '0-0-0',
                'away_rank': 0,
                'scraped_at': int(time.time()),
                'is_simulated': True,
                'simulation_type': 'toilet_bowl_round1'
            })
            
            # Track winners and losers
            if team1_points > team2_points:
                week14_winners.append(team1)
                week14_losers.append(team2)
            else:
                week14_winners.append(team2)
                week14_losers.append(team1)
        
        # Week 15: Semifinals (winners vs winners, losers vs losers)
        if len(week14_winners) >= 2 and len(week14_losers) >= 2:
            # Winners bracket semifinal
            winner1 = week14_winners[0]
            winner2 = week14_winners[1]
            winner1_points = get_real_score(winner1['team_id'], '15')
            winner2_points = get_real_score(winner2['team_id'], '15')
            
            toilet_games.append({
                'game_id': f"{season}15{winner1['team_id']}{winner2['team_id']}_toilet_winners",
                'season': season,
                'week': '15',
                'home_team': winner1['team_name'],
                'home_team_id': winner1['team_id'],
                'home_points': winner1_points,
                'home_record': '0-0-0',
                'home_rank': 0,
                'away_team': winner2['team_name'],
                'away_team_id': winner2['team_id'],
                'away_points': winner2_points,
                'away_record': '0-0-0',
                'away_rank': 0,
                'scraped_at': int(time.time()),
                'is_simulated': True,
                'simulation_type': 'toilet_bowl_winners'
            })
            
            # Losers bracket semifinal
            loser1 = week14_losers[0]
            loser2 = week14_losers[1]
            loser1_points = get_real_score(loser1['team_id'], '15')
            loser2_points = get_real_score(loser2['team_id'], '15')
            
            toilet_games.append({
                'game_id': f"{season}15{loser1['team_id']}{loser2['team_id']}_toilet_losers",
                'season': season,
                'week': '15',
                'home_team': loser1['team_name'],
                'home_team_id': loser1['team_id'],
                'home_points': loser1_points,
                'home_record': '0-0-0',
                'home_rank': 0,
                'away_team': loser2['team_name'],
                'away_team_id': loser2['team_id'],
                'away_points': loser2_points,
                'away_record': '0-0-0',
                'away_rank': 0,
                'scraped_at': int(time.time()),
                'is_simulated': True,
                'simulation_type': 'toilet_bowl_losers'
            })
            
            # Track week 15 results
            week15_winners_bracket_winner = winner1 if winner1_points > winner2_points else winner2
            week15_winners_bracket_loser = winner2 if winner1_points > winner2_points else winner1
            week15_losers_bracket_winner = loser1 if loser1_points > loser2_points else loser2
            week15_losers_bracket_loser = loser2 if loser1_points > loser2_points else loser1
            
            # Week 16: Championship and 3rd place games
            # Championship game (winners bracket final)
            champ_winner_points = get_real_score(week15_winners_bracket_winner['team_id'], '16')
            champ_loser_points = get_real_score(week15_winners_bracket_loser['team_id'], '16')
            
            toilet_games.append({
                'game_id': f"{season}16{week15_winners_bracket_winner['team_id']}{week15_winners_bracket_loser['team_id']}_toilet_champ",
                'season': season,
                'week': '16',
                'home_team': week15_winners_bracket_winner['team_name'],
                'home_team_id': week15_winners_bracket_winner['team_id'],
                'home_points': champ_winner_points,
                'home_record': '0-0-0',
                'home_rank': 0,
                'away_team': week15_winners_bracket_loser['team_name'],
                'away_team_id': week15_winners_bracket_loser['team_id'],
                'away_points': champ_loser_points,
                'away_record': '0-0-0',
                'away_rank': 0,
                'scraped_at': int(time.time()),
                'is_simulated': True,
                'simulation_type': 'toilet_bowl_championship'
            })
            
            # 3rd place game (losers bracket final)
            third_winner_points = get_real_score(week15_losers_bracket_winner['team_id'], '16')
            third_loser_points = get_real_score(week15_losers_bracket_loser['team_id'], '16')
            
            toilet_games.append({
                'game_id': f"{season}16{week15_losers_bracket_winner['team_id']}{week15_losers_bracket_loser['team_id']}_toilet_third",
                'season': season,
                'week': '16',
                'home_team': week15_losers_bracket_winner['team_name'],
                'home_team_id': week15_losers_bracket_winner['team_id'],
                'home_points': third_winner_points,
                'home_record': '0-0-0',
                'home_rank': 0,
                'away_team': week15_losers_bracket_loser['team_name'],
                'away_team_id': week15_losers_bracket_loser['team_id'],
                'away_points': third_loser_points,
                'away_record': '0-0-0',
                'away_rank': 0,
                'scraped_at': int(time.time()),
                'is_simulated': True,
                'simulation_type': 'toilet_bowl_third_place'
            })
        
        if not toilet_games:
            print(f"No toilet bowl games created for season {season}")
            return
        
        # Remove any existing toilet bowl games
        existing_games = [g for g in existing_games if not (g.get('simulation_type', '').startswith('toilet_bowl'))]
        
        # Add toilet bowl games to existing schedule
        all_games = existing_games + toilet_games
        
        # Ensure fieldnames include all keys from all games
        all_fieldnames = set()
        for game in all_games:
            all_fieldnames.update(game.keys())
        fieldnames = list(all_fieldnames)
        
        # Save updated schedule
        with open(schedule_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for game in all_games:
                writer.writerow(game)
        
        print(f"✓ Injected {len(toilet_games)} toilet bowl games into schedule for season {season}")
        for game in toilet_games:
            print(f"  Week {game['week']}: {game['home_team']} ({game['home_points']}) vs {game['away_team']} ({game['away_points']}) ({game['simulation_type']})")
    
    def _inject_toilet_bowl_games_with_placeholders(self, season: int) -> None:
        """
        Inject toilet bowl games with placeholder scores for 2011-2017 seasons.
        """
        # Load the playoff brackets to get toilet bowl games
        brackets_path = self._get_processed_path(season).parent / 'playoff_brackets.json'
        if not brackets_path.exists():
            print(f"No playoff brackets found for season {season}")
            return
            
        with open(brackets_path, 'r') as f:
            brackets = json.load(f)
        
        # Get toilet bowl games from brackets
        toilet_bracket = brackets.get('consolation_bracket', {})
        toilet_games = []
        
        # Week 15 toilet bowl games (from round_1 if they have _toilet suffix)
        for game in toilet_bracket.get('round_1', []):
            if '_toilet' in game.get('game_id', ''):
                toilet_games.append({
                    'game_id': game['game_id'].replace('_toilet', ''),  # Remove suffix for schedule
                    'season': season,
                    'week': '15',
                    'home_team': game['home_team']['name'],
                    'home_team_id': game['home_team']['id'],
                    'home_points': game['home_team']['points'],
                    'home_record': '0-0-0',  # Placeholder
                    'home_rank': 0,  # Placeholder
                    'away_team': game['away_team']['name'],
                    'away_team_id': game['away_team']['id'],
                    'away_points': game['away_team']['points'],
                    'away_record': '0-0-0',  # Placeholder
                    'away_rank': 0,  # Placeholder
                    'scraped_at': int(time.time()),
                    'is_simulated': True,  # Flag to indicate this is a simulated game
                    'simulation_type': 'toilet_bowl'
                })
        
        # Week 16 toilet bowl games (all games in toilet_bowl round are toilet bowl games)
        for game in toilet_bracket.get('toilet_bowl', []):
            toilet_games.append({
                'game_id': game['game_id'].replace('_toilet', ''),  # Remove suffix for schedule
                'season': season,
                'week': '16',
                'home_team': game['home_team']['name'],
                'home_team_id': game['home_team']['id'],
                'home_points': game['home_team']['points'],
                'home_record': '0-0-0',  # Placeholder
                'home_rank': 0,  # Placeholder
                'away_team': game['away_team']['name'],
                'away_team_id': game['away_team']['id'],
                'away_points': game['away_team']['points'],
                'away_record': '0-0-0',  # Placeholder
                'away_rank': 0,  # Placeholder
                'scraped_at': int(time.time()),
                'is_simulated': True,  # Flag to indicate this is a simulated game
                'simulation_type': 'toilet_bowl'
            })
        
        if not toilet_games:
            print(f"No toilet bowl games found for season {season}")
            return
        
        # Load existing schedule
        schedule_path = self._get_processed_path(season)
        if not schedule_path.exists():
            print(f"No schedule found for season {season}")
            return
            
        existing_games = []
        with open(schedule_path, 'r') as f:
            reader = csv.DictReader(f)
            existing_games = list(reader)
        
        # Add toilet bowl games to existing schedule
        all_games = existing_games + toilet_games
        
        # Save updated schedule
        with open(schedule_path, 'w', newline='') as f:
            fieldnames = list(existing_games[0].keys()) + ['is_simulated', 'simulation_type']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write existing games (with None for new fields)
            for game in existing_games:
                game['is_simulated'] = False
                game['simulation_type'] = None
                writer.writerow(game)
            
            # Write toilet bowl games
            for game in toilet_games:
                writer.writerow(game)
        
        print(f"✓ Injected {len(toilet_games)} toilet bowl games into schedule for season {season}")
        for game in toilet_games:
            print(f"  Week {game['week']}: {game['home_team']} vs {game['away_team']} (simulated)")

    def inject_mediocre_bowl_games(self, season: int) -> None:
        """
        Inject simulated mediocre bowl games into the schedule CSV.
        The mediocre bowl is the same two teams (seeds 7-8) playing each other in weeks 14, 15, and 16.
        The points for each team are set to their real score from their actual game that week.
        Always uses the 7th and 8th place teams from the regular season standings.
        Uses api_client_v2_optimized to get actual team scores including kicker and defense points.
        Args:
            season: The NFL season year
        """
        # Load playoff brackets to get middle teams (seeds 7 and 8)
        brackets_path = self.processed_dir / f"{season}" / "playoff_brackets.json"
        if not brackets_path.exists():
            print(f"No playoff brackets found for season {season}")
            return
        import json
        with open(brackets_path, 'r') as f:
            brackets = json.load(f)
        
        # Get middle teams from playoff brackets
        middle_teams = brackets.get('middle_teams', [])
        if len(middle_teams) < 2:
            print(f"Not enough middle teams in playoff brackets for season {season}")
            return
        
        # DEBUG: Print the teams selected for mediocre bowl
        print("=== DEBUG: Teams selected for mediocre bowl ===")
        print("Seed 7:", middle_teams[0]['team_name'], middle_teams[0]['team_id'])
        print("Seed 8:", middle_teams[1]['team_name'], middle_teams[1]['team_id'])
        team7 = middle_teams[0]  # Seed 7
        team8 = middle_teams[1]  # Seed 8
        # Build team dicts for compatibility
        team1 = {'team_id': team7['team_id'], 'team_name': team7['team_name']}
        team2 = {'team_id': team8['team_id'], 'team_name': team8['team_name']}
        # Load existing schedule
        schedule_path = self._get_processed_path(season)
        if not schedule_path.exists():
            print(f"No schedule found for season {season}")
            return
        import csv
        existing_games = []
        with open(schedule_path, 'r') as f:
            reader = csv.DictReader(f)
            existing_games = list(reader)
        # Use api_client_v2 to get real scores
        try:
            from src.ingest.nfl.api_client_v2_optimized import NFLFantasyMultiTableScraper
            api_client = NFLFantasyMultiTableScraper()
            league_id = self._get_league_id(str(season))
        except ImportError:
            print("api_client_v2_optimized not available, falling back to schedule data")
            api_client = None
        # Helper to get real score for a team in a week
        def get_real_score(team_id, week):
            if api_client:
                # Use optimized API client to get actual score with all player types
                try:
                    team_data = api_client.get_team_data(league_id, team_id, season, int(week), force_refresh=False)
                    if team_data and 'players' in team_data:
                        # Count only starters' points (exclude bench players)
                        starter_points = sum(
                            player.get('fantasy_points', 0.0) 
                            for player in team_data['players'] 
                            if player.get('lineup_status') == 'starter'
                        )
                        return starter_points
                except Exception as e:
                    print(f"Error getting score for team {team_id} week {week}: {e}")
            
            # Fallback to schedule data
            for g in existing_games:
                if g['week'] == week and (g['home_team_id'] == team_id or g['away_team_id'] == team_id):
                    return float(g['home_points']) if g['home_team_id'] == team_id else float(g['away_points'])
            return 0.0
        # Create mediocre bowl games for weeks 14, 15, and 16
        mediocre_games = []
        for week in ['14', '15', '16']:
            # Alternate home/away teams
            if week == '14':
                home_team = team1
                away_team = team2
            elif week == '15':
                home_team = team2
                away_team = team1
            else:  # week 16
                home_team = team1
                away_team = team2
            home_points = get_real_score(home_team['team_id'], week)
            away_points = get_real_score(away_team['team_id'], week)
            mediocre_games.append({
                'game_id': f"{season}{week}{home_team['team_id']}{away_team['team_id']}_mediocre",
                'season': season,
                'week': week,
                'home_team': home_team['team_name'],
                'home_team_id': home_team['team_id'],
                'home_points': home_points,
                'home_record': '0-0-0',  # Placeholder
                'home_rank': 0,  # Placeholder
                'away_team': away_team['team_name'],
                'away_team_id': away_team['team_id'],
                'away_points': away_points,
                'away_record': '0-0-0',  # Placeholder
                'away_rank': 0,  # Placeholder
                'scraped_at': int(time.time()),
                'is_simulated': True,  # Flag to indicate this is a simulated game
                'simulation_type': 'mediocre_bowl'
            })
        if not mediocre_games:
            print(f"No mediocre bowl games created for season {season}")
            return
        # Remove any existing mediocre bowl games
        existing_games = [g for g in existing_games if not (g.get('simulation_type') == 'mediocre_bowl')]
        # Add mediocre bowl games to existing schedule
        all_games = existing_games + mediocre_games
        # Ensure fieldnames include all keys from all games
        all_fieldnames = set()
        for game in all_games:
            all_fieldnames.update(game.keys())
        fieldnames = list(all_fieldnames)
        # Save updated schedule
        with open(schedule_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for game in all_games:
                writer.writerow(game)
        print(f"✓ Injected {len(mediocre_games)} mediocre bowl games into schedule for season {season}")
        for game in mediocre_games:
            print(f"  Week {game['week']}: {game['home_team']} ({game['home_points']}) vs {game['away_team']} ({game['away_points']}) (simulated)")

    def _calculate_mediocre_bowl_results_2018_plus(self, season: int) -> Dict:
        """
        Calculate mediocre bowl results for 2018+ seasons (3-week format).
        
        Args:
            season: The NFL season year
            
        Returns:
            Dictionary with team results for mediocre bowl
        """
        # Load the mediocre bowl standings
        mediocre_bowl_path = self.processed_dir / f"{season}" / "mediocre_bowl_standings.json"
        if not mediocre_bowl_path.exists():
            return {}
            
        with open(mediocre_bowl_path, 'r') as f:
            mediocre_bowl_data = json.load(f)
            
        # Convert to the expected format
        results = {}
        for team in mediocre_bowl_data:
            team_id = team['team_id']
            results[team_id] = {
                'team_name': team['team_name'],
                'total_points': team['total_points'],
                'week_14_points': team.get('week_14_points', 0.0),
                'week_15_points': team['week_15_points'],
                'week_16_points': team['week_16_points']
            }
            
        return results

# Main execution block for testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NFL Schedule Scraper")
    parser.add_argument('--season', type=int, default=2012, help='NFL season year (default: 2012)')
    parser.add_argument('--force-refresh', action='store_true', help='Force refresh cached data')
    args = parser.parse_args()
    
    print("=== NFL Schedule Scraper Test ===")
    
    # Initialize the scraper
    scraper = NFLScheduleIngest()
    
    try:
        # Test with specified season
        season = args.season
        print(f"\nTesting schedule scraping for {season} season...")
        
        # Test fetching a specific week with force refresh
        print(f"\nTesting fresh fetch for Week 1...")
        week1_data = scraper.fetch_weekly_schedule(season, 1, force_refresh=args.force_refresh)
        print(f"Week 1 games: {len(week1_data.get('games', []))}")
        for game in week1_data.get('games', []):
            print(f"  {game['home_team']} vs {game['away_team']} - {game['home_points']} to {game['away_points']}")
        
        # Fetch and process the entire season
        scraper.fetch_and_process_season(season)
        
        # Generate playoff brackets
        print(f"\nGenerating playoff brackets for {season}...")
        scraper.save_playoff_brackets(season)
        
        # Generate postseason standings
        print(f"\nGenerating postseason standings for {season}...")
        scraper.save_postseason_standings(season)
        
        # Generate mediocre bowl standings (for bragging rights)
        print(f"\nGenerating mediocre bowl standings for {season}...")
        scraper.save_mediocre_bowl_standings(season)
        
        # Generate all standings
        print(f"\nGenerating all standings for {season}...")
        scraper.save_all_standings(season)
        
        print(f"\n✅ Successfully completed all operations for {season} season!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        scraper.close()
        print("\n=== Test Complete ===") 
        print("\n=== Test Complete ===") 