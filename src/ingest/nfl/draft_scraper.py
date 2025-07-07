#!/usr/bin/env python3
"""
Improved Draft Scraper for Stag Brotherhood League
Enhanced requests-based approach with multiple parsing strategies.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from urllib.parse import parse_qs, urlparse
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

class ImprovedDraftScraper:
    def __init__(self, league_id: str = "864504", data_dir: str = "data/processed"):
        self.league_id = league_id
        self.base_url = "https://fantasy.nfl.com"
        self.data_dir = Path(data_dir)
        # Draft data will be organized by year in subdirectories
        self.base_draft_dir = self.data_dir / "drafts"
        self.base_draft_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        
        # Configure league IDs for different seasons
        self.league_ids = {
            "2011": "400491",  # Original league
            "2012+": "864504"  # New league starting 2012
        }
        
        # Enhanced headers to look more like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def _get_league_id(self, year: int) -> str:
        """Get the appropriate league ID for a given year."""
        year_str = str(year)
        return self.league_ids.get(year_str, self.league_ids["2012+"])
    
    def scrape_draft(self, year: int) -> pd.DataFrame:
        """Main method to scrape draft data with multiple strategies."""
        print(f"🚀 Scraping {year} draft...")
        
        # Strategy 1: Try auction draft with pagination
        df = self._scrape_auction_with_pagination(year)
        if not df.empty:
            print(f"✅ Found {len(df)} auction picks with pagination")
            return df
        
        # Strategy 2: Try the main draft results page
        df = self._scrape_main_page(year)
        if not df.empty:
            print(f"✅ Found {len(df)} picks on main page")
            return df
        
        # Strategy 3: Try different URL patterns
        df = self._scrape_alternative_urls(year)
        if not df.empty:
            print(f"✅ Found {len(df)} picks with alternative URLs")
            return df
        
        # Strategy 4: Try round-by-round scraping (snake draft)
        df = self._scrape_snake_by_round(year)
        if not df.empty:
            print(f"✅ Found {len(df)} picks by round (snake draft)")
            return df
        
        print(f"❌ No draft data found for {year}")
        return pd.DataFrame()
    
    def _scrape_main_page(self, year: int) -> pd.DataFrame:
        """Scrape the main draft results page."""
        league_id = self._get_league_id(year)
        url = f"{self.base_url}/league/{league_id}/history/{year}/draftresults"
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Save HTML for debugging
            year_draft_dir = self.base_draft_dir / str(year)
            year_draft_dir.mkdir(parents=True, exist_ok=True)
            debug_file = year_draft_dir / f"debug_main.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"💾 Saved debug HTML: {debug_file}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try auction parsing first (most likely for recent years)
            draft_data = self._parse_auction_strategy(soup, year)
            if draft_data:
                print(f"✅ Found {len(draft_data)} auction picks on main page")
                return pd.DataFrame(draft_data)
            
            # If no auction data, try snake draft strategies
            strategies = [
                self._parse_snake_strategy_1,  # Snake draft strategy 1
                self._parse_snake_strategy_2,  # Snake draft strategy 2
                self._parse_snake_strategy_3,  # Snake draft strategy 3
            ]
            
            for i, strategy in enumerate(strategies, 1):
                print(f"🔍 Trying snake parsing strategy {i}...")
                draft_data = strategy(soup, year)
                if draft_data:
                    df = pd.DataFrame(draft_data)
                    print(f"✅ Strategy {i} found {len(df)} picks")
                    return df
            
            print("❌ All parsing strategies failed")
            return pd.DataFrame()
            
        except Exception as e:
            print(f"❌ Error scraping main page: {e}")
            return pd.DataFrame()
    
    def _scrape_auction_with_pagination(self, year: int) -> pd.DataFrame:
        """Scrape auction draft with pagination through all nomination pages."""
        all_draft_data = []
        
        # Try to get all nomination pages (1-12, 13-24, etc.)
        nomination_pages = []
        
        # First, try to get the main page to see how many pages there are
        league_id = self._get_league_id(year)
        main_url = f"{self.base_url}/league/{league_id}/history/{year}/draftresults"
        try:
            response = self.session.get(main_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for pagination links
            pagination_links = soup.find_all('a', href=re.compile(r'draftResultsDetail=\d+'))
            for link in pagination_links:
                href = link.get('href', '')
                detail_match = re.search(r'draftResultsDetail=(\d+)', href)
                if detail_match:
                    page_num = int(detail_match.group(1))
                    if page_num not in nomination_pages:
                        nomination_pages.append(page_num)
            
            # If no pagination found, try pages 1-16 (typical auction draft size)
            if not nomination_pages:
                nomination_pages = list(range(1, 17))
            
            print(f"Found {len(nomination_pages)} nomination pages: {nomination_pages}")
            
        except Exception as e:
            print(f"Error getting pagination info: {e}")
            # Fallback to pages 1-16
            nomination_pages = list(range(1, 17))
        
        # Scrape each nomination page
        for page_num in sorted(nomination_pages):
            url = f"{self.base_url}/league/{league_id}/history/{year}/draftresults?draftResultsDetail={page_num}&draftResultsTab=nomination&draftResultsType=results"
            
            try:
                print(f"🔍 Scraping nomination page {page_num}...")
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                page_data = self._parse_auction_strategy(soup, year)
                
                if page_data:
                    all_draft_data.extend(page_data)
                    print(f"✅ Page {page_num}: {len(page_data)} picks")
                else:
                    print(f"⚠️  Page {page_num}: No picks found")
                    # If we've found some data but this page is empty, we might be done
                    if len(all_draft_data) > 0:
                        break
                
                time.sleep(1)  # Be nice to the server
                
            except Exception as e:
                print(f"❌ Error fetching page {page_num}: {e}")
                break
        
        return pd.DataFrame(all_draft_data)
    
    def _parse_auction_strategy(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse auction draft format."""
        draft_data = []
        
        # Look for auction draft structure
        auction_items = soup.find_all('li', class_='isAuction')
        
        if not auction_items:
            print("No auction items found")
            return []
        
        print(f"Found {len(auction_items)} auction items")
        
        for i, item in enumerate(auction_items, 1):
            try:
                print(f"--- Processing auction item {i} ---")
                
                # Extract nomination number
                count_span = item.find('span', class_='count')
                if not count_span:
                    print("  No count span found")
                    continue
                
                nomination_text = count_span.get_text(strip=True)
                nomination_match = re.match(r'(\d+)\.', nomination_text)
                if not nomination_match:
                    print(f"  No nomination match for: {nomination_text}")
                    continue
                
                nomination_number = int(nomination_match.group(1))
                print(f"  Nomination text: {nomination_text}")
                print(f"  Nomination number: {nomination_number}")
                
                # Extract player information - try multiple selectors
                player_link = None
                player_selectors = [
                    'a.playerCard.playerName.playerNameFull',
                    'a.playerCard.playerName',
                    'a[class*="playerCard"][class*="playerName"]',
                    'a[href*="/players/cardhistory"]'
                ]
                
                for selector in player_selectors:
                    player_link = item.select_one(selector)
                    if player_link:
                        print(f"  Found player link with selector: {selector}")
                        break
                
                if not player_link:
                    print("  No player link found")
                    continue
                
                player_name = player_link.get_text(strip=True)
                player_id = self._extract_player_id(player_link.get('href', ''))
                print(f"  Player name: {player_name}")
                print(f"  Player ID: {player_id}")
                
                # Extract position and NFL team
                position_em = item.find('em')
                if position_em:
                    pos_team_text = position_em.get_text(strip=True)
                    pos_team_match = re.match(r'([A-Z]+)\s*-\s*([A-Z]+)', pos_team_text)
                    if pos_team_match:
                        position = pos_team_match.group(1)
                        nfl_team = pos_team_match.group(2)
                    else:
                        position = ""
                        nfl_team = ""
                else:
                    position = ""
                    nfl_team = ""
                
                print(f"  Position: {position}, NFL Team: {nfl_team}")
                
                # Extract team information
                team_link = item.find('a', class_='teamName')
                team_name = team_link.get_text(strip=True) if team_link else ""
                team_id = self._extract_team_id(team_link.get('href', '')) if team_link else ""
                print(f"  Team name: {team_name}")
                print(f"  Team ID: {team_id}")
                
                # Extract owner name
                owner_li = item.find('li', class_='first last')
                owner_name = owner_li.get_text(strip=True) if owner_li else ""
                print(f"  Owner name: {owner_name}")
                
                # Extract auction cost
                cost_span = item.find('span', class_='auctionCost')
                if cost_span:
                    cost_text = cost_span.get_text(strip=True)
                    cost_match = re.search(r'\$(\d+)', cost_text)
                    auction_cost = int(cost_match.group(1)) if cost_match else None
                else:
                    auction_cost = None
                print(f"  Auction cost: ${auction_cost}")
                
                draft_data.append({
                    'year': year,
                    'nomination': nomination_number,
                    'player_id': player_id,
                    'player_name': player_name,
                    'position': position,
                    'nfl_team': nfl_team,
                    'fantasy_team_id': team_id,
                    'fantasy_team_name': team_name,
                    'owner_name': owner_name,
                    'auction_cost': auction_cost,
                    'draft_type': 'auction',
                    'scraped_at': datetime.now().isoformat()
                })
                
                print(f"  ✅ Added draft data for {player_name}")
                
            except Exception as e:
                print(f"  Error parsing auction item: {e}")
                continue
        
        print(f"Total draft data items: {len(draft_data)}")
        return draft_data
    
    def _parse_snake_strategy_1(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse snake draft strategy 1: Look for list items with pick patterns."""
        draft_data = []
        
        # Look for the specific snake draft structure from 2020
        draft_items = soup.find_all('li', class_=lambda x: x and ('first' in x or x == ''))
        print(f"Found {len(draft_items)} potential draft items")
        
        for i, item in enumerate(draft_items):
            try:
                print(f"  Processing item {i+1}: {item.get('class', 'no-class')}")
                # Extract pick number
                count_span = item.find('span', class_='count')
                if not count_span:
                    print(f"    No count span found")
                    continue
                
                pick_text = count_span.get_text(strip=True)
                pick_match = re.match(r'(\d+)\.', pick_text)
                if not pick_match:
                    continue
                
                pick_number = int(pick_match.group(1))
                
                # Extract player information
                player_link = item.find('a', class_='playerCard playerName playerNameFull')
                if not player_link:
                    continue
                
                player_name = player_link.get_text(strip=True)
                player_id = self._extract_player_id(player_link.get('href', ''))
                
                # Extract position and NFL team
                position_em = item.find('em')
                if position_em:
                    pos_team_text = position_em.get_text(strip=True)
                    pos_team_match = re.match(r'([A-Z]+)\s*-\s*([A-Z]+)', pos_team_text)
                    if pos_team_match:
                        position = pos_team_match.group(1)
                        nfl_team = pos_team_match.group(2)
                    else:
                        position = ""
                        nfl_team = ""
                else:
                    position = ""
                    nfl_team = ""
                
                # Extract team information
                team_link = item.find('a', class_='teamName')
                team_name = team_link.get_text(strip=True) if team_link else ""
                team_id = self._extract_team_id(team_link.get('href', '')) if team_link else ""
                
                # Extract owner name
                owner_li = item.find('li', class_='first last')
                owner_name = owner_li.get_text(strip=True) if owner_li else ""
                
                draft_data.append({
                    'year': year,
                    'round': (pick_number - 1) // 12 + 1,  # Calculate round from pick number
                    'pick': pick_number,
                    'overall_pick': pick_number,
                    'player_id': player_id,
                    'player_name': player_name,
                    'position': position,
                    'nfl_team': nfl_team,
                    'fantasy_team_id': team_id,
                    'fantasy_team_name': team_name,
                    'owner_name': owner_name,
                    'draft_type': 'snake',
                    'scraped_at': datetime.now().isoformat()
                })
                
            except Exception as e:
                print(f"Error parsing snake draft item: {e}")
                continue
        
        return draft_data
    
    def _parse_snake_strategy_2(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse snake draft strategy 2: Look for table rows."""
        draft_data = []
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    # Look for player links in cells
                    for cell in cells:
                        player_link = cell.find('a', href=re.compile(r'/players/'))
                        if player_link:
                            pick_data = self._extract_pick_data_from_cell(cell, row, year)
                            if pick_data:
                                draft_data.append(pick_data)
                                break
        
        return draft_data
    
    def _parse_snake_strategy_3(self, soup: BeautifulSoup, year: int) -> List[Dict]:
        """Parse snake draft strategy 3: Find any element with player links."""
        draft_data = []
        
        # Find all player links
        player_links = soup.find_all('a', href=re.compile(r'/players/'))
        
        for link in player_links:
            # Get the parent element that might contain the full pick info
            parent = link.parent
            if parent:
                text = parent.get_text(strip=True)
                if re.search(r'\d+\.', text):  # Has a pick number
                    pick_data = self._extract_pick_data_from_player_link(link, parent, year)
                    if pick_data:
                        draft_data.append(pick_data)
        
        return draft_data
    
    def _scrape_alternative_urls(self, year: int) -> pd.DataFrame:
        """Try alternative URL patterns."""
        league_id = self._get_league_id(year)
        alternative_urls = [
            f"{self.base_url}/league/{league_id}/history/{year}/draftresults?draftResultsType=results",
            f"{self.base_url}/league/{league_id}/history/{year}/draftresults?draftResultsDetail=1",
        ]
        
        for url in alternative_urls:
            try:
                print(f"🔍 Trying alternative URL: {url}")
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                draft_data = self._parse_auction_strategy(soup, year)
                
                if draft_data:
                    df = pd.DataFrame(draft_data)
                    print(f"✅ Alternative URL found {len(df)} picks")
                    return df
                
            except Exception as e:
                print(f"❌ Alternative URL failed: {e}")
                continue
        
        return pd.DataFrame()
    
    def _scrape_snake_by_round(self, year: int) -> pd.DataFrame:
        """Scrape snake draft by looping through all rounds."""
        all_picks = []
        max_rounds = 20  # Most leagues have <= 20 rounds
        league_id = self._get_league_id(year)
        for round_num in range(1, max_rounds + 1):
            url = f"{self.base_url}/league/{league_id}/history/{year}/draftresults?draftResultsDetail={round_num}&draftResultsTab=round&draftResultsType=results"
            try:
                print(f"🔍 Fetching round {round_num}...")
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                picks = self._parse_snake_round(soup, year, round_num)
                print(f"  Found {len(picks)} picks in round {round_num}")
                if not picks:
                    # If no picks found, assume draft is over
                    break
                all_picks.extend(picks)
                time.sleep(0.5)
            except Exception as e:
                print(f"  Error fetching round {round_num}: {e}")
                break
        # Ensure all columns are present for consistency
        df = pd.DataFrame(all_picks)
        expected_cols = [
            'year', 'nomination', 'round', 'pick', 'overall_pick', 'player_id', 'player_name', 'position', 'nfl_team',
            'fantasy_team_id', 'fantasy_team_name', 'owner_name', 'auction_cost', 'draft_type', 'scraped_at'
        ]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        return df[expected_cols] if not df.empty else df

    def _parse_snake_round(self, soup: BeautifulSoup, year: int, round_num: int) -> list:
        """Parse all picks in a single round of a snake draft."""
        picks = []
        wrap = soup.find('div', class_='wrap')
        if not wrap:
            print(f"    No <div class='wrap'> found in round {round_num}")
            return picks
        ul = wrap.find('ul')
        if not ul:
            print(f"    No <ul> found in <div class='wrap'> for round {round_num}")
            return picks
        li_items = ul.find_all('li', recursive=False)
        print(f"    Found {len(li_items)} pick <li> items in round {round_num}")
        for i, item in enumerate(li_items):
            try:
                print(f"      Processing li item {i+1}: {item.get('class', 'no-class')}")
                # Print the first 100 characters of the li content for debugging
                li_text = item.get_text(strip=True)[:100]
                print(f"        Li content: {li_text}")
                
                # Try to find count span first
                count_span = item.find('span', class_='count')
                if count_span:
                    pick_text = count_span.get_text(strip=True)
                    pick_match = re.match(r'(\d+)\.', pick_text)
                    if pick_match:
                        pick_number = int(pick_match.group(1))
                        print(f"        Found pick number from span: {pick_number}")
                    else:
                        print(f"        No valid pick number in span")
                        continue
                else:
                    # Fallback: extract pick number from text content
                    pick_match = re.match(r'(\d+)\.', li_text)
                    if not pick_match:
                        print(f"        No pick number found in text")
                        continue
                    pick_number = int(pick_match.group(1))
                    print(f"        Found pick number from text: {pick_number}")
                player_link = item.find('a', class_='playerCard playerName playerNameFull')
                if not player_link:
                    print(f"        No player link found with class 'playerCard playerName playerNameFull'")
                    # Try alternative selector
                    player_link = item.find('a', class_='playerCard')
                    if not player_link:
                        print(f"        No player link found with class 'playerCard'")
                        continue
                    else:
                        print(f"        Found player link with class 'playerCard'")
                else:
                    print(f"        Found player link with full class")
                # Try to get player name from text content first
                player_name = player_link.get_text(strip=True)
                # If text is empty, try to get from img alt attribute
                if not player_name:
                    img = player_link.find('img')
                    if img:
                        player_name = img.get('alt', '')
                player_id = self._extract_player_id(player_link.get('href', ''))
                position_em = item.find('em')
                if position_em:
                    pos_team_text = position_em.get_text(strip=True)
                    pos_team_match = re.match(r'([A-Z]+)\s*-\s*([A-Z]+)', pos_team_text)
                    if pos_team_match:
                        position = pos_team_match.group(1)
                        nfl_team = pos_team_match.group(2)
                    else:
                        position = ""
                        nfl_team = ""
                else:
                    position = ""
                    nfl_team = ""
                team_link = item.find('a', class_='teamName')
                team_name = team_link.get_text(strip=True) if team_link else ""
                team_id = self._extract_team_id(team_link.get('href', '')) if team_link else ""
                owner_li = item.find('li', class_='first last')
                owner_name = owner_li.get_text(strip=True) if owner_li else ""
                picks.append({
                    'year': year,
                    'nomination': None,
                    'round': round_num,
                    'pick': pick_number,
                    'overall_pick': (round_num - 1) * 12 + pick_number,
                    'player_id': player_id,
                    'player_name': player_name,
                    'position': position,
                    'nfl_team': nfl_team,
                    'fantasy_team_id': team_id,
                    'fantasy_team_name': team_name,
                    'owner_name': owner_name,
                    'auction_cost': None,
                    'draft_type': 'snake',
                    'scraped_at': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"    Error parsing pick: {e}")
                continue
        return picks
    
    def _extract_pick_data_from_match(self, match, element, year: int) -> Optional[Dict]:
        """Extract pick data from regex match."""
        try:
            pick_number = int(match.group(1))
            
            # Extract player information
            player_link = element.find('a', href=re.compile(r'/players/'))
            if not player_link:
                return None
            
            player_name = player_link.get_text(strip=True)
            player_id = self._extract_player_id(player_link['href'])
            
            # Extract position and NFL team from match groups
            if len(match.groups()) >= 4:
                position = match.group(3)
                nfl_team = match.group(4)
            else:
                # Fallback: extract from text
                pos_team_match = re.search(r'([A-Z]+)\s*-\s*([A-Z]+)', element.get_text())
                position = pos_team_match.group(1) if pos_team_match else ""
                nfl_team = pos_team_match.group(2) if pos_team_match else ""
            
            # Extract team information
            team_link = element.find('a', href=re.compile(r'/league/\d+/history/\d+/teamhome'))
            team_name = team_link.get_text(strip=True) if team_link else ""
            team_id = self._extract_team_id(team_link['href']) if team_link else ""
            
            return {
                'year': year,
                'round': 1,  # Default for snake draft
                'pick': pick_number,
                'overall_pick': pick_number,
                'player_id': player_id,
                'player_name': player_name,
                'position': position,
                'nfl_team': nfl_team,
                'fantasy_team_id': team_id,
                'fantasy_team_name': team_name,
                'draft_type': 'snake',
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error extracting pick data from match: {e}")
            return None
    
    def _extract_pick_data_from_cell(self, cell, row, year: int) -> Optional[Dict]:
        """Extract pick data from table cell."""
        try:
            player_link = cell.find('a', href=re.compile(r'/players/'))
            if not player_link:
                return None
            
            player_name = player_link.get_text(strip=True)
            player_id = self._extract_player_id(player_link['href'])
            
            # Get text from all cells in the row
            row_text = ' '.join([c.get_text(strip=True) for c in row.find_all(['td', 'th'])])
            
            # Extract pick number
            pick_match = re.search(r'(\d+)', row_text)
            pick_number = int(pick_match.group(1)) if pick_match else 1
            
            # Extract position and NFL team
            pos_team_match = re.search(r'([A-Z]+)\s*-\s*([A-Z]+)', row_text)
            position = pos_team_match.group(1) if pos_team_match else ""
            nfl_team = pos_team_match.group(2) if pos_team_match else ""
            
            # Extract team information
            team_link = row.find('a', href=re.compile(r'/league/\d+/history/\d+/teamhome'))
            team_name = team_link.get_text(strip=True) if team_link else ""
            team_id = self._extract_team_id(team_link['href']) if team_link else ""
            
            return {
                'year': year,
                'round': 1,
                'pick': pick_number,
                'overall_pick': pick_number,
                'player_id': player_id,
                'player_name': player_name,
                'position': position,
                'nfl_team': nfl_team,
                'fantasy_team_id': team_id,
                'fantasy_team_name': team_name,
                'draft_type': 'snake',
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error extracting pick data from cell: {e}")
            return None
    
    def _extract_pick_data_from_player_link(self, link, parent, year: int) -> Optional[Dict]:
        """Extract pick data from player link."""
        try:
            player_name = link.get_text(strip=True)
            player_id = self._extract_player_id(link['href'])
            
            text = parent.get_text(strip=True)
            
            # Extract pick number
            pick_match = re.search(r'(\d+)\.', text)
            if not pick_match:
                return None
            
            pick_number = int(pick_match.group(1))
            
            # Extract position and NFL team
            pos_team_match = re.search(r'([A-Z]+)\s*-\s*([A-Z]+)', text)
            position = pos_team_match.group(1) if pos_team_match else ""
            nfl_team = pos_team_match.group(2) if pos_team_match else ""
            
            # Extract team information
            team_link = parent.find('a', href=re.compile(r'/league/\d+/history/\d+/teamhome'))
            team_name = team_link.get_text(strip=True) if team_link else ""
            team_id = self._extract_team_id(team_link['href']) if team_link else ""
            
            return {
                'year': year,
                'round': 1,
                'pick': pick_number,
                'overall_pick': pick_number,
                'player_id': player_id,
                'player_name': player_name,
                'position': position,
                'nfl_team': nfl_team,
                'fantasy_team_id': team_id,
                'fantasy_team_name': team_name,
                'draft_type': 'snake',
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error extracting pick data from player link: {e}")
            return None
    
    def _extract_player_id(self, url: str) -> Optional[str]:
        """Extract player ID from URL."""
        if not url:
            return None
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return params.get('playerId', [None])[0]
    
    def _extract_team_id(self, url: str) -> Optional[str]:
        """Extract team ID from URL."""
        if not url:
            return None
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return params.get('teamId', [None])[0]
    
    def save_draft_data(self, df: pd.DataFrame, year: int, format: str = 'both'):
        """Save draft data to file(s)."""
        if df.empty:
            print(f"⚠️  No data to save for {year}")
            return
        
        # Create year-specific directory
        year_draft_dir = self.base_draft_dir / str(year)
        year_draft_dir.mkdir(parents=True, exist_ok=True)
        
        if format in ['csv', 'both']:
            csv_file = year_draft_dir / "draft_results.csv"
            df.to_csv(csv_file, index=False)
            print(f"✅ Saved CSV: {csv_file}")
        
        if format in ['json', 'both']:
            json_file = year_draft_dir / "draft_results.json"
            df.to_json(json_file, orient='records', indent=2)
            print(f"✅ Saved JSON: {json_file}")
    
    def generate_draft_report(self, df: pd.DataFrame, year: int) -> str:
        """Generate a draft report."""
        if df.empty:
            return f"# {year} Draft Report\n\nNo data available."
        
        report = []
        report.append(f"# {year} Stag Brotherhood League Draft Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Summary
        report.append("## Draft Summary")
        report.append(f"- **Total Picks**: {len(df)}")
        report.append(f"- **Draft Type**: {df['draft_type'].iloc[0] if 'draft_type' in df.columns else 'Unknown'}")
        
        if 'auction_cost' in df.columns and df['auction_cost'].notna().any():
            total_spent = df['auction_cost'].sum()
            avg_cost = df['auction_cost'].mean()
            report.append(f"- **Total Spent**: ${total_spent:,}")
            report.append(f"- **Average Cost**: ${avg_cost:.2f}")
        
        report.append("")
        
        # Position breakdown
        if 'position' in df.columns:
            report.append("## Position Breakdown")
            pos_counts = df['position'].value_counts()
            for pos, count in pos_counts.items():
                percentage = (count / len(df)) * 100
                report.append(f"- **{pos}**: {count} picks ({percentage:.1f}%)")
            report.append("")
        
        # Team breakdown
        if 'fantasy_team_name' in df.columns:
            report.append("## Team Pick Counts")
            team_counts = df['fantasy_team_name'].value_counts()
            for team, count in team_counts.items():
                report.append(f"- **{team}**: {count} picks")
            report.append("")
        
        # Sample picks
        report.append("## Sample Picks")
        for _, row in df.head(10).iterrows():
            if 'auction_cost' in df.columns and pd.notna(row.get('auction_cost')):
                report.append(f"- {row['player_name']} ({row['position']} - {row['nfl_team']}) → {row['fantasy_team_name']} (${row['auction_cost']})")
            else:
                report.append(f"- {row['player_name']} ({row['position']} - {row['nfl_team']}) → {row['fantasy_team_name']}")
        
        return "\n".join(report)

def main():
    """Test the improved draft scraper."""
    scraper = ImprovedDraftScraper()
    
    # Test years
    test_years = [2022, 2021, 2020]
    
    for year in test_years:
        print(f"\n{'='*50}")
        print(f"Testing {year} Draft")
        print(f"{'='*50}")
        
        try:
            df = scraper.scrape_draft(year)
            
            if not df.empty:
                print(f"✅ Successfully scraped {len(df)} picks")
                print(f"Sample data:")
                print(df.head())
                
                # Save data
                scraper.save_draft_data(df, year)
                
                # Generate report
                report = scraper.generate_draft_report(df, year)
                year_draft_dir = scraper.base_draft_dir / str(year)
                report_file = year_draft_dir / "draft_report.md"
                with open(report_file, 'w') as f:
                    f.write(report)
                print(f"✅ Generated report: {report_file}")
                
            else:
                print(f"❌ No data found for {year}")
        
        except Exception as e:
            print(f"❌ Error scraping {year}: {e}")
        
        time.sleep(2)  # Be nice to the server

if __name__ == "__main__":
    main() 