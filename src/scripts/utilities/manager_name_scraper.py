#!/usr/bin/env python3
"""
Manager Name Scraper

This module scrapes the actual manager names from the NFL Fantasy Managers page
to get accurate manager data instead of trying to extract it from team names.
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Optional
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import argparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ManagerNameScraper:
    """Scrapes manager names from NFL Fantasy Managers page."""
    
    def __init__(self, data_dir: str = "data"):
        """Initialize the scraper."""
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.base_url = "https://fantasy.nfl.com"
        
    def get_managers_page(self, league_id: str, season: int) -> str:
        """Get the managers page URL."""
        return f"{self.base_url}/league/{league_id}/history/{season}/owners"
    
    def scrape_manager_names(self, league_id: str, season: int) -> Dict[str, Dict]:
        """Scrape manager names and team info from the managers page."""
        url = self.get_managers_page(league_id, season)
        logger.info(f"Scraping manager names from: {url}")
        
        # Use a simple approach with requests first, then selenium if needed
        try:
            import requests
            from bs4 import BeautifulSoup
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Save the raw HTML for debugging
            raw_path = self.raw_dir / "schedule" / str(season) / f"managers_page_{league_id}.html"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return self._parse_manager_table(soup, league_id, season)
            
        except Exception as e:
            logger.warning(f"Requests failed, trying Selenium: {e}")
            return self._scrape_with_selenium(url, league_id, season)
    
    def _scrape_with_selenium(self, url: str, league_id: str, season: int) -> Dict[str, Dict]:
        """Scrape using Selenium as fallback."""
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        try:
            driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # Save the raw HTML
            raw_path = self.raw_dir / "schedule" / str(season) / f"managers_page_{league_id}_selenium.html"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            
            # Parse the page
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            return self._parse_manager_table(soup, league_id, season)
            
        finally:
            driver.quit()
    
    def _parse_manager_table(self, soup, league_id: str, season: int) -> Dict[str, Dict]:
        """Parse the manager table from the HTML."""
        managers = {}
        
        # Look for the managers table - it has class "tableType-team hasGroups"
        table = soup.find('table', class_='tableType-team')
        if not table:
            logger.warning("Could not find managers table")
            return managers
        
        # Find all rows in the tbody
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("Could not find table body")
            return managers
        
        rows = tbody.find_all('tr')
        logger.info(f"Found {len(rows)} manager rows")
        
        for row in rows:
            # Each row has class like "team-1", "team-6", etc.
            row_class = row.get('class', [])
            team_class = [c for c in row_class if c.startswith('team-')]
            
            if not team_class:
                continue
                
            team_id = team_class[0].replace('team-', '')
            
            # Get all cells in the row
            cells = row.find_all('td')
            if len(cells) < 7:  # Need at least 7 columns
                continue
            
            # Extract team name from first cell
            team_cell = cells[0]
            team_link = team_cell.find('a', class_='teamName')
            if team_link:
                team_name = team_link.get_text(strip=True)
            else:
                team_name = ""
            
            # Extract manager name and user ID from second cell
            manager_cell = cells[1]
            manager_span = manager_cell.find('span', class_='userName')
            if manager_span:
                manager_name = manager_span.get_text(strip=True)
                # Extract user ID from class attribute
                user_id = None
                for cls in manager_span.get('class', []):
                    if cls.startswith('userId-'):
                        user_id = cls.replace('userId-', '')
                        break
            else:
                manager_name = ""
                user_id = None
            
            # Extract additional data
            waiver_priority = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            moves = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            trades = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            last_activity = cells[6].get_text(strip=True) if len(cells) > 6 else ""
            
            if team_id and team_name and manager_name:
                managers[team_id] = {
                    "team_id": team_id,
                    "team_name": team_name,
                    "manager_name": manager_name,
                    "user_id": user_id,
                    "league_id": league_id,
                    "season": season,
                    "waiver_priority": waiver_priority,
                    "moves": moves,
                    "trades": trades,
                    "last_activity": last_activity
                }
        
        logger.info(f"Successfully parsed {len(managers)} managers")
        return managers
    
    def save_manager_data(self, managers: Dict[str, Dict], season: int) -> None:
        """Save manager data to JSON file."""
        output_path = self.processed_dir / "schedule" / str(season) / "managers.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(managers, f, indent=2)
        
        logger.info(f"Manager data saved to {output_path}")
    
    def create_manager_mapping_csv(self, managers: Dict[str, Dict], season: int) -> None:
        """Create a CSV mapping file for easy reference."""
        output_path = self.processed_dir / "schedule" / str(season) / "manager_mapping.csv"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['team_id', 'team_name', 'manager_name', 'user_id', 'waiver_priority', 'moves', 'trades', 'last_activity'])
            
            for team_id, data in managers.items():
                writer.writerow([
                    data['team_id'],
                    data['team_name'],
                    data['manager_name'],
                    data.get('user_id', ''),
                    data.get('waiver_priority', ''),
                    data.get('moves', ''),
                    data.get('trades', ''),
                    data.get('last_activity', '')
                ])
        
        logger.info(f"Manager mapping CSV saved to {output_path}")


def main():
    """Main function to scrape manager names."""
    parser = argparse.ArgumentParser(description="Scrape NFL Fantasy manager names for a given season.")
    parser.add_argument('--season', type=int, default=2012, help='Season year (default: 2012)')
    parser.add_argument('--league_id', type=str, default='864504', help='League ID (default: 864504)')
    args = parser.parse_args()

    scraper = ManagerNameScraper()
    league_id = args.league_id
    season = args.season

    print(f"=== Scraping Manager Names for {season} Season ===")
    managers = scraper.scrape_manager_names(league_id, season)
    if managers:
        print(f"\n✅ Found {len(managers)} managers:")
        for team_id, data in managers.items():
            print(f"   Team {team_id}: {data['team_name']} - {data['manager_name']}")
        # Save the data
        scraper.save_manager_data(managers, season)
        scraper.create_manager_mapping_csv(managers, season)
        print(f"\n📁 Manager data saved to:")
        print(f"   JSON: data/processed/schedule/{season}/managers.json")
        print(f"   CSV: data/processed/schedule/{season}/manager_mapping.csv")
    else:
        print("❌ No managers found")


if __name__ == "__main__":
    main() 