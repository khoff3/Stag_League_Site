#!/usr/bin/env python3
"""
Enhanced NFL Fantasy Football Scraper
Properly handles offense, kicker, and defense tables with accurate starter/bench detection
"""

import os
import json
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup


class NFLFantasyMultiTableScraper:
    def __init__(self, base_url: str = "https://fantasy.nfl.com"):
        self.base_url = base_url
        self.raw_dir = Path("data/raw")
        self.processed_dir = Path("data/processed")
        
        # Create directories if they don't exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Define roster positions (not bench)
        self.roster_positions = {
            'QB', 'RB', 'WR', 'TE', 'W/R', 'W/R/T', 'Q/W/R/T', 
            'K', 'DEF', 'D/ST', 'IDP', 'DL', 'LB', 'DB'
        }
    
    def get_team_data(self, league_id: str, team_id: str, season: int, week: int, force_refresh: bool = False) -> Optional[Dict]:
        """
        Main method to scrape all player tables (offense, kicker, defense) for a team.
        """
        # Check cache first
        if not force_refresh and self._is_cached(season, week, team_id):
            return self._load_from_cache(season, week, team_id)
        
        # Configure Chrome options
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=options)
        
        try:
            # Navigate to the page with weekly stats parameters
            url = f"{self.base_url}/league/{league_id}/history/{season}/teamhome?statCategory=stats&statSeason={season}&statType=weekStats&statWeek={week}&teamId={team_id}&week={week}"
            print(f"Fetching URL: {url}")
            driver.get(url)
            
            # Wait for page to load
            wait = WebDriverWait(driver, 30)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            time.sleep(5)
            
            # Find all player tables
            all_players = []
            
            # Method 1: Look for tables with specific IDs
            table_ids = ['tableWrapOffense', 'tableWrapKicker', 'tableWrapDefense']
            
            for table_id in table_ids:
                try:
                    table_wrapper = driver.find_element(By.ID, table_id)
                    table = table_wrapper.find_element(By.TAG_NAME, "table")
                    print(f"\nFound table: {table_id}")
                    
                    # Determine table type from ID
                    if 'offense' in table_id.lower():
                        players = self._extract_offense_data(table)
                    elif 'kicker' in table_id.lower():
                        players = self._extract_kicker_data(table)
                    elif 'defense' in table_id.lower():
                        players = self._extract_defense_data(table)
                    else:
                        players = []
                    
                    print(f"Extracted {len(players)} players from {table_id}")
                    all_players.extend(players)
                    
                except NoSuchElementException:
                    print(f"Table {table_id} not found")
            
            # Method 2: If specific IDs not found, look for all player tables
            if not all_players:
                print("\nFalling back to generic table search...")
                
                # Parse HTML once and reuse
                page_html = driver.page_source
                soup = BeautifulSoup(page_html, 'html.parser')
                tables = soup.find_all('table')
                print(f"Found {len(tables)} tables on the page.")
                
                # Process each table based on headers
                for i, table in enumerate(tables):
                    print(f"Processing table {i+1}/{len(tables)}")
                    
                    # Get headers for this table
                    all_rows = table.find_all('tr')
                    
                    if len(all_rows) < 2:
                        continue
                    
                    # Check first two rows for headers
                    header_row = None
                    header_row_index = 0
                    
                    for row_idx, row in enumerate(all_rows[:2]):
                        cells = row.find_all(['th', 'td'])
                        if cells:
                            header_text = " ".join(cell.get_text().strip().lower() for cell in cells)
                            
                            # Look for position-related headers first (POS)
                            if any(keyword in header_text for keyword in ['pos', 'position']):
                                header_row = row
                                header_row_index = row_idx
                                break
                            
                            # Fallback: Look for player-related headers
                            if any(keyword in header_text for keyword in ['offense', 'player', 'name', 'qb', 'rb', 'wr']):
                                header_row = row
                                header_row_index = row_idx
                                break
                    
                    if not header_row:
                        continue
                    
                    # Extract headers
                    header_cells = header_row.find_all(['th', 'td'])
                    headers = [cell.get_text().strip().lower() for cell in header_cells]
                    
                    # Identify table type based on headers
                    header_text = " ".join(headers)
                    if any(word in header_text for word in ['offense', 'passing', 'rushing', 'receiving']):
                        print(f"  Table {i+1}: Offense table")
                        players = self._extract_offense_data_with_headers(table, headers, header_row_index)
                    elif any(word in header_text for word in ['kicker', 'pat', 'fg made', '0-19', '20-29']):
                        print(f"  Table {i+1}: Kicker table")
                        players = self._extract_kicker_data_with_headers(table, headers, header_row_index)
                    elif any(word in header_text for word in ['defense team', 'sack', 'tackles', 'turnover', 'int']):
                        print(f"  Table {i+1}: Defense table")
                        players = self._extract_defense_data_with_headers(table, headers, header_row_index)
                    else:
                        print(f"  Table {i+1}: Unknown table type")
                        players = []
                    
                    print(f"  Extracted {len(players)} players")
                    all_players.extend(players)
            
            # Count starters and bench
            starters = [p for p in all_players if p.get('lineup_status') == 'starter']
            bench = [p for p in all_players if p.get('lineup_status') == 'bench']
            
            print(f"\nTotal players: {len(all_players)} ({len(starters)} starters, {len(bench)} bench)")
            
            if all_players:
                result = {
                    "players": all_players,
                    "team_stats": {
                        "total_players": len(all_players),
                        "starters": len(starters),
                        "bench": len(bench),
                        "total_points": sum(p.get('fantasy_points', 0) for p in starters)
                    },
                    "source": "html_scraping"
                }
                self._save_to_cache(season, week, team_id, result)
                return result
            else:
                print("No player data extracted")
                return None
                
        except Exception as e:
            print(f"Scraping failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            driver.quit()
    
    def _identify_table_type(self, table) -> str:
        """Identify table type by examining headers"""
        try:
            headers = table.find_elements(By.TAG_NAME, "th")
            header_text = " ".join(h.text.lower() for h in headers)
            
            # Check for specific keywords
            if any(word in header_text for word in ['made', '0-19', '20-29', '30-39', 'fg']):
                return 'kicker'
            elif any(word in header_text for word in ['sack', 'int', 'fum rec', 'pts allow']):
                return 'defense'
            else:
                return 'offense'
        except:
            return 'unknown'
    
    def _extract_offense_data(self, table) -> List[Dict]:
        """Extract offensive player data (QB, RB, WR, TE)"""
        players = []
        
        try:
            table_html = table.get_attribute('outerHTML')
            soup = BeautifulSoup(table_html, 'html.parser')
            
            # Find all rows
            all_rows = soup.find_all('tr')
            if len(all_rows) < 2:
                return []
            
            # Find header row - check first two rows
            header_row = None
            header_row_index = 0
            
            for i, row in enumerate(all_rows[:2]):
                cells = row.find_all(['th', 'td'])
                if cells:
                    header_text = " ".join(cell.get_text().strip().lower() for cell in cells)
                    print(f"Offense table row {i} headers: {[cell.get_text().strip() for cell in cells]}")
                    
                    # Look for position-related headers first (POS)
                    if any(keyword in header_text for keyword in ['pos', 'position']):
                        header_row = row
                        header_row_index = i
                        print(f"Using row {i} as header row (found POS)")
                        break
                    
                    # Fallback: Look for player-related headers
                    if any(keyword in header_text for keyword in ['offense', 'player', 'name', 'qb', 'rb', 'wr']):
                        header_row = row
                        header_row_index = i
                        print(f"Using row {i} as header row (found player keywords)")
                        break
            
            if not header_row:
                print("Could not identify header row for offense table")
                return []
            
            # Extract headers
            header_cells = header_row.find_all(['th', 'td'])
            headers = [cell.get_text().strip().lower() for cell in header_cells]
            print(f"Offense table final headers: {headers}")
            
            # Map columns for offense
            column_map = self._map_offense_columns(headers)
            
            # Extract player data
            data_rows = all_rows[header_row_index + 1:]
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                player = self._extract_player_from_offense_row(cells, column_map, row)
                if player and player.get('name'):
                    players.append(player)
            
        except Exception as e:
            print(f"Error extracting offense data: {e}")
        
        return players
    
    def _extract_kicker_data(self, table) -> List[Dict]:
        """Extract kicker data"""
        players = []
        
        try:
            table_html = table.get_attribute('outerHTML')
            soup = BeautifulSoup(table_html, 'html.parser')
            
            # Find all rows
            all_rows = soup.find_all('tr')
            if len(all_rows) < 2:
                return []
            
            # Find header row - check first two rows
            header_row = None
            header_row_index = 0
            
            for i, row in enumerate(all_rows[:2]):
                cells = row.find_all(['th', 'td'])
                if cells:
                    header_text = " ".join(cell.get_text().strip().lower() for cell in cells)
                    print(f"Kicker table row {i} headers: {[cell.get_text().strip() for cell in cells]}")
                    
                    # Look for position-related headers first (POS)
                    if any(keyword in header_text for keyword in ['pos', 'position']):
                        header_row = row
                        header_row_index = i
                        print(f"Using row {i} as header row (found POS)")
                        break
                    
                    # Fallback: Look for kicker-related headers
                    if any(keyword in header_text for keyword in ['kicker', 'pat', 'fg made', '0-19', '20-29']):
                        header_row = row
                        header_row_index = i
                        print(f"Using row {i} as header row (found kicker keywords)")
                        break
            
            if not header_row:
                print("Could not identify header row for kicker table")
                return []
            
            # Extract headers
            header_cells = header_row.find_all(['th', 'td'])
            headers = [cell.get_text().strip().lower() for cell in header_cells]
            print(f"Kicker table final headers: {headers}")
            
            # Map columns for kickers
            column_map = self._map_kicker_columns(headers)
            
            # Extract player data
            data_rows = all_rows[header_row_index + 1:]
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                player = self._extract_player_from_kicker_row(cells, column_map, row)
                if player and player.get('name'):
                    players.append(player)
            
        except Exception as e:
            print(f"Error extracting kicker data: {e}")
        
        return players
    
    def _extract_defense_data(self, table) -> List[Dict]:
        """Extract defense/special teams data"""
        players = []
        
        try:
            table_html = table.get_attribute('outerHTML')
            soup = BeautifulSoup(table_html, 'html.parser')
            
            # Find all rows
            all_rows = soup.find_all('tr')
            if len(all_rows) < 2:
                return []
            
            # Find header row - check first two rows
            header_row = None
            header_row_index = 0
            
            for i, row in enumerate(all_rows[:2]):
                cells = row.find_all(['th', 'td'])
                if cells:
                    header_text = " ".join(cell.get_text().strip().lower() for cell in cells)
                    print(f"Defense table row {i} headers: {[cell.get_text().strip() for cell in cells]}")
                    
                    # Look for position-related headers first (POS)
                    if any(keyword in header_text for keyword in ['pos', 'position']):
                        header_row = row
                        header_row_index = i
                        print(f"Using row {i} as header row (found POS)")
                        break
                    
                    # Fallback: Look for defense-related headers
                    if any(keyword in header_text for keyword in ['defense', 'sack', 'tackles', 'turnover', 'int']):
                        header_row = row
                        header_row_index = i
                        print(f"Using row {i} as header row (found defense keywords)")
                        break
            
            if not header_row:
                print("Could not identify header row for defense table")
                return []
            
            # Extract headers
            header_cells = header_row.find_all(['th', 'td'])
            headers = [cell.get_text().strip().lower() for cell in header_cells]
            print(f"Defense table final headers: {headers}")
            
            # Map columns for defense
            column_map = self._map_defense_columns(headers)
            
            # Extract player data
            data_rows = all_rows[header_row_index + 1:]
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                player = self._extract_player_from_defense_row(cells, column_map, row)
                if player and player.get('name'):
                    players.append(player)
            
        except Exception as e:
            print(f"Error extracting defense data: {e}")
        
        return players
    
    def _map_offense_columns(self, headers: List[str]) -> Dict[str, int]:
        """Map column headers for offensive players"""
        column_map = {}
        yds_count = 0
        td_count = 0
        
        for i, header in enumerate(headers):
            header_lower = header.lower().strip()
            
            if header_lower == 'pos':
                column_map['position'] = i
            elif header_lower == 'offense':
                column_map['name'] = i
            elif header_lower == 'opp':
                column_map['opponent'] = i
            elif header_lower == 'status':
                column_map['status'] = i
            elif header_lower == 'points':
                column_map['fantasy_points'] = i
            elif header_lower == 'yds':
                if yds_count == 0:
                    column_map['passing_yards'] = i
                elif yds_count == 1:
                    column_map['rushing_yards'] = i
                elif yds_count == 2:
                    column_map['receiving_yards'] = i
                yds_count += 1
            elif header_lower == 'td':
                if td_count == 0:
                    column_map['passing_tds'] = i
                elif td_count == 1:
                    column_map['rushing_tds'] = i
                elif td_count == 2:
                    column_map['receiving_tds'] = i
                td_count += 1
            elif header_lower == 'int':
                column_map['interceptions'] = i
            elif header_lower == '2pt':
                column_map['two_point_conversions'] = i
            elif header_lower == 'lost':
                column_map['fumbles_lost'] = i
        
        return column_map
    
    def _map_kicker_columns(self, headers: List[str]) -> Dict[str, int]:
        """Map column headers for kickers"""
        column_map = {}
        
        for i, header in enumerate(headers):
            header_lower = header.lower().strip()
            
            if header_lower == 'pos':
                column_map['position'] = i
            elif header_lower == 'kicker':
                column_map['name'] = i
            elif header_lower == 'opp':
                column_map['opponent'] = i
            elif header_lower == 'status':
                column_map['status'] = i
            elif header_lower == 'points':
                column_map['fantasy_points'] = i
            elif header_lower == 'made':
                column_map['fg_made'] = i
            elif header_lower == '0-19':
                column_map['fg_0_19'] = i
            elif header_lower == '20-29':
                column_map['fg_20_29'] = i
            elif header_lower == '30-39':
                column_map['fg_30_39'] = i
            elif header_lower == '40-49':
                column_map['fg_40_49'] = i
            elif header_lower == '50+':
                column_map['fg_50_plus'] = i
            elif header_lower == 'pat':
                column_map['pat_made'] = i
        
        return column_map
    
    def _map_defense_columns(self, headers: List[str]) -> Dict[str, int]:
        """Map column headers for defense/ST"""
        column_map = {}
        
        for i, header in enumerate(headers):
            header_lower = header.lower().strip()
            
            if header_lower == 'pos':
                column_map['position'] = i
            elif 'defense' in header_lower:
                column_map['name'] = i
            elif header_lower == 'opp':
                column_map['opponent'] = i
            elif header_lower == 'status':
                column_map['status'] = i
            elif header_lower == 'points':
                column_map['fantasy_points'] = i
            elif header_lower == 'sack':
                column_map['sacks'] = i
            elif header_lower == 'int':
                column_map['interceptions'] = i
            elif 'fum' in header_lower and 'rec' in header_lower:
                column_map['fumble_recoveries'] = i
            elif header_lower == 'saf':
                column_map['safeties'] = i
            elif header_lower == 'td' and 'def_tds' not in column_map:
                column_map['def_tds'] = i
            elif 'pts' in header_lower and 'allow' in header_lower:
                column_map['points_allowed'] = i
        
        return column_map
    
    def _extract_player_from_offense_row(self, cells: List, column_map: Dict[str, int], row) -> Dict:
        """Extract offensive player from row"""
        player = {}
        
        # First, get position to determine if starter/bench
        if 'position' in column_map and column_map['position'] < len(cells):
            pos_text = cells[column_map['position']].get_text().strip()
            player['position'] = pos_text
            player['lineup_status'] = 'bench' if pos_text == 'BN' else 'starter'
        
        # Extract other fields
        for field, col_index in column_map.items():
            if col_index < len(cells):
                cell_text = cells[col_index].get_text().strip()
                
                if field == 'name':
                    # Parse "Player Name POS - TEAM" format
                    name_parts = cell_text.split(' - ')
                    if len(name_parts) > 1:
                        name_pos = name_parts[0].rsplit(' ', 1)
                        if len(name_pos) > 1:
                            player['name'] = name_pos[0].strip()
                        else:
                            player['name'] = name_parts[0].strip()
                        player['nfl_team'] = name_parts[1].strip()
                    else:
                        player['name'] = cell_text
                
                elif field == 'fantasy_points':
                    player[field] = self._parse_float(cell_text)
                
                elif field in ['passing_yards', 'rushing_yards', 'receiving_yards']:
                    player[field] = self._parse_int(cell_text)
                
                elif field in ['passing_tds', 'rushing_tds', 'receiving_tds', 'interceptions', 
                             'two_point_conversions', 'fumbles_lost']:
                    player[field] = self._parse_int(cell_text)
                
                elif field == 'status':
                    if ',' in cell_text:
                        parts = cell_text.split(',', 1)
                        player['game_result'] = parts[0].strip()
                        player['game_score'] = parts[1].strip()
        
        # Add player type
        player['player_type'] = 'offense'
        
        return player
    
    def _extract_player_from_kicker_row(self, cells: List, column_map: Dict[str, int], row) -> Dict:
        """Extract kicker from row"""
        player = {}
        
        # First, get position
        if 'position' in column_map and column_map['position'] < len(cells):
            pos_text = cells[column_map['position']].get_text().strip()
            player['position'] = pos_text
            player['lineup_status'] = 'bench' if pos_text == 'BN' else 'starter'
        
        # Extract other fields
        for field, col_index in column_map.items():
            if col_index < len(cells):
                cell_text = cells[col_index].get_text().strip()
                
                if field == 'name':
                    # Parse "Player Name POS - TEAM" format
                    name_parts = cell_text.split(' - ')
                    if len(name_parts) > 1:
                        name_pos = name_parts[0].rsplit(' ', 1)
                        if len(name_pos) > 1:
                            player['name'] = name_pos[0].strip()
                        else:
                            player['name'] = name_parts[0].strip()
                        player['nfl_team'] = name_parts[1].strip()
                    else:
                        player['name'] = cell_text
                
                elif field == 'fantasy_points':
                    player[field] = self._parse_float(cell_text)
                
                elif field in ['fg_made', 'fg_0_19', 'fg_20_29', 'fg_30_39', 'fg_40_49', 'fg_50_plus', 'pat_made']:
                    player[field] = self._parse_int(cell_text)
                
                elif field == 'status':
                    if ',' in cell_text:
                        parts = cell_text.split(',', 1)
                        player['game_result'] = parts[0].strip()
                        player['game_score'] = parts[1].strip()
        
        # Add player type
        player['player_type'] = 'kicker'
        
        return player
    
    def _extract_player_from_defense_row(self, cells: List, column_map: Dict[str, int], row) -> Dict:
        """Extract defense/ST from row"""
        player = {}
        
        # First, get position
        if 'position' in column_map and column_map['position'] < len(cells):
            pos_text = cells[column_map['position']].get_text().strip()
            player['position'] = pos_text
            player['lineup_status'] = 'bench' if pos_text == 'BN' else 'starter'
        
        # Extract other fields
        for field, col_index in column_map.items():
            if col_index < len(cells):
                cell_text = cells[col_index].get_text().strip()
                
                if field == 'name':
                    # Defense names are simpler - just "Team Name DEF"
                    player['name'] = cell_text.replace(' DEF', '').replace(' D/ST', '')
                    player['nfl_team'] = player['name']  # For defense, team is the name
                
                elif field == 'fantasy_points':
                    player[field] = self._parse_float(cell_text)
                
                elif field in ['sacks', 'interceptions', 'fumble_recoveries', 'safeties', 
                             'def_tds', 'points_allowed']:
                    player[field] = self._parse_int(cell_text)
                
                elif field == 'status':
                    if ',' in cell_text:
                        parts = cell_text.split(',', 1)
                        player['game_result'] = parts[0].strip()
                        player['game_score'] = parts[1].strip()
        
        # Add player type
        player['player_type'] = 'defense'
        
        return player
    
    def _parse_float(self, text: str) -> float:
        """Parse float value from text, handling '-' and empty values"""
        if text == '-' or text == '':
            return 0.0
        match = re.search(r'(-?\d+\.?\d*)', text)
        return float(match.group(1)) if match else 0.0
    
    def _parse_int(self, text: str) -> int:
        """Parse int value from text, handling '-' and empty values"""
        if text == '-' or text == '':
            return 0
        match = re.search(r'(-?\d+)', text)
        return int(match.group(1)) if match else 0
    
    def print_team_summary(self, team_data: Dict) -> None:
        """Print a nice summary of team data"""
        if not team_data or 'players' not in team_data:
            print("No team data to display")
            return
        
        players = team_data['players']
        
        # Separate by type and status
        starters = [p for p in players if p.get('lineup_status') == 'starter']
        bench = [p for p in players if p.get('lineup_status') == 'bench']
        
        offense_starters = [p for p in starters if p.get('player_type') == 'offense']
        kicker_starters = [p for p in starters if p.get('player_type') == 'kicker']
        defense_starters = [p for p in starters if p.get('player_type') == 'defense']
        
        print("\n" + "="*80)
        print("STARTING LINEUP")
        print("="*80)
        
        # Print offense
        if offense_starters:
            print("\nOFFENSE:")
            print(f"{'Pos':<5} {'Player':<25} {'Team':<5} {'Points':<8} {'Pass':<10} {'Rush':<10} {'Rec':<10}")
            print("-"*78)
            for p in offense_starters:
                print(f"{p.get('position', 'N/A'):<5} "
                      f"{p.get('name', 'N/A')[:24]:<25} "
                      f"{p.get('nfl_team', 'N/A'):<5} "
                      f"{p.get('fantasy_points', 0):<8.1f} "
                      f"{str(p.get('passing_yards', '-')):<10} "
                      f"{str(p.get('rushing_yards', '-')):<10} "
                      f"{str(p.get('receiving_yards', '-')):<10}")
        
        # Print kicker
        if kicker_starters:
            print("\nKICKER:")
            print(f"{'Pos':<5} {'Player':<25} {'Team':<5} {'Points':<8} {'FG Made':<10} {'PAT':<10}")
            print("-"*78)
            for p in kicker_starters:
                print(f"{p.get('position', 'N/A'):<5} "
                      f"{p.get('name', 'N/A')[:24]:<25} "
                      f"{p.get('nfl_team', 'N/A'):<5} "
                      f"{p.get('fantasy_points', 0):<8.1f} "
                      f"{str(p.get('fg_made', '-')):<10} "
                      f"{str(p.get('pat_made', '-')):<10}")
        
        # Print defense
        if defense_starters:
            print("\nDEFENSE/ST:")
            print(f"{'Pos':<5} {'Team':<25} {'Points':<8} {'Sacks':<8} {'Int':<8} {'Pts Allow':<10}")
            print("-"*78)
            for p in defense_starters:
                print(f"{p.get('position', 'N/A'):<5} "
                      f"{p.get('name', 'N/A')[:24]:<25} "
                      f"{p.get('fantasy_points', 0):<8.1f} "
                      f"{str(p.get('sacks', '-')):<8} "
                      f"{str(p.get('interceptions', '-')):<8} "
                      f"{str(p.get('points_allowed', '-')):<10}")
        
        # Print bench
        if bench:
            print("\n" + "="*80)
            print("BENCH")
            print("="*80)
            print(f"{'Pos':<5} {'Player':<25} {'Team':<5} {'Type':<10} {'Points':<8}")
            print("-"*78)
            for p in bench:
                print(f"BN    "
                      f"{p.get('name', 'N/A')[:24]:<25} "
                      f"{p.get('nfl_team', 'N/A'):<5} "
                      f"{p.get('player_type', 'N/A'):<10} "
                      f"{p.get('fantasy_points', 0):<8.1f}")
        
        # Print totals
        print("\n" + "="*80)
        print("TOTALS")
        print("="*80)
        total_starters_points = sum(p.get('fantasy_points', 0) for p in starters)
        total_bench_points = sum(p.get('fantasy_points', 0) for p in bench)
        print(f"Starters: {len(starters)} players, {total_starters_points:.1f} points")
        print(f"Bench: {len(bench)} players, {total_bench_points:.1f} points")
        print(f"Total: {len(players)} players, {total_starters_points + total_bench_points:.1f} points")
    
    def export_to_csv(self, team_data: Dict, output_path: str) -> None:
        """Export team data to CSV with all player types"""
        if not team_data or 'players' not in team_data:
            print("No data to export")
            return
        
        df = pd.DataFrame(team_data['players'])
        
        # Reorder columns for better readability
        column_order = [
            'lineup_status', 'position', 'name', 'nfl_team', 'player_type',
            'fantasy_points', 'game_result', 'game_score',
            # Offense stats
            'passing_yards', 'passing_tds', 'interceptions',
            'rushing_yards', 'rushing_tds',
            'receiving_yards', 'receiving_tds',
            'two_point_conversions', 'fumbles_lost',
            # Kicker stats
            'fg_made', 'fg_0_19', 'fg_20_29', 'fg_30_39', 'fg_40_49', 'fg_50_plus', 'pat_made',
            # Defense stats
            'sacks', 'fumble_recoveries', 'safeties', 'def_tds', 'points_allowed'
        ]
        
        # Only include columns that exist
        columns_to_use = [col for col in column_order if col in df.columns]
        df = df[columns_to_use]
        
        df.to_csv(output_path, index=False)
        print(f"Exported to {output_path}")
    
    # Include cache methods from original
    def _is_cached(self, season: int, week: int, team_id: str) -> bool:
        """Check if data is cached"""
        cache_path = self.raw_dir / f"{season}" / f"week_{week:02d}" / f"team_{team_id}.json"
        return cache_path.exists()
    
    def _load_from_cache(self, season: int, week: int, team_id: str) -> Optional[Dict]:
        """Load data from cache"""
        cache_path = self.raw_dir / f"{season}" / f"week_{week:02d}" / f"team_{team_id}.json"
        try:
            with open(cache_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading from cache: {e}")
            return None
    
    def _save_to_cache(self, season: int, week: int, team_id: str, data: Dict) -> None:
        """Save data to cache"""
        cache_path = self.raw_dir / f"{season}" / f"week_{week:02d}" / f"team_{team_id}.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _extract_offense_data_with_headers(self, table, headers: List[str], header_row_index: int) -> List[Dict]:
        """Extract offensive player data with pre-detected headers"""
        players = []
        
        try:
            # Find all rows (table is already a BeautifulSoup object)
            all_rows = table.find_all('tr')
            if len(all_rows) < header_row_index + 2:
                return []
            
            # Map columns for offense
            column_map = self._map_offense_columns(headers)
            
            # Extract player data
            data_rows = all_rows[header_row_index + 1:]
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                player = self._extract_player_from_offense_row(cells, column_map, row)
                if player and player.get('name'):
                    players.append(player)
            
        except Exception as e:
            print(f"Error extracting offense data: {e}")
        
        return players
    
    def _extract_kicker_data_with_headers(self, table, headers: List[str], header_row_index: int) -> List[Dict]:
        """Extract kicker data with pre-detected headers"""
        players = []
        
        try:
            # Find all rows (table is already a BeautifulSoup object)
            all_rows = table.find_all('tr')
            if len(all_rows) < header_row_index + 2:
                return []
            
            # Map columns for kickers
            column_map = self._map_kicker_columns(headers)
            
            # Extract player data
            data_rows = all_rows[header_row_index + 1:]
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                player = self._extract_player_from_kicker_row(cells, column_map, row)
                if player and player.get('name'):
                    players.append(player)
            
        except Exception as e:
            print(f"Error extracting kicker data: {e}")
        
        return players
    
    def _extract_defense_data_with_headers(self, table, headers: List[str], header_row_index: int) -> List[Dict]:
        """Extract defense data with pre-detected headers"""
        players = []
        
        try:
            # Find all rows (table is already a BeautifulSoup object)
            all_rows = table.find_all('tr')
            if len(all_rows) < header_row_index + 2:
                return []
            
            # Map columns for defense
            column_map = self._map_defense_columns(headers)
            
            # Extract player data
            data_rows = all_rows[header_row_index + 1:]
            
            for row in data_rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                player = self._extract_player_from_defense_row(cells, column_map, row)
                if player and player.get('name'):
                    players.append(player)
            
        except Exception as e:
            print(f"Error extracting defense data: {e}")
        
        return players


# Usage Example
if __name__ == "__main__":
    # Initialize the scraper
    scraper = NFLFantasyMultiTableScraper()
    
    # Your league parameters
    league_id = "864504"
    team_id = "1"
    season = 2012
    week = 1
    
    print("=== NFL Fantasy Multi-Table Scraper ===")
    print(f"Scraping Team {team_id} for {season} Week {week}")
    
    # Scrape team data
    team_data = scraper.get_team_data(league_id, team_id, season, week, force_refresh=True)
    
    if team_data:
        # Print nice summary
        scraper.print_team_summary(team_data)
        
        # Export to CSV
        output_path = f"team_{team_id}_week_{week}.csv"
        scraper.export_to_csv(team_data, output_path)
    else:
        print("Failed to scrape team data")