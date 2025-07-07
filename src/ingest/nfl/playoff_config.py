"""
Configuration for playoff structure and standings.
"""

from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class PlayoffConfig:
    """Configuration for playoff structure and standings."""
    
    regular_season_weeks: int
    playoff_start_week: int
    playoff_end_week: int
    winners_bracket_size: int
    consolation_bracket_size: int
    has_middle_teams: bool = False
    has_divisions: bool = False
    has_byes: bool = False
    
    # Championship week game types and their labels
    championship_week_games: Dict[str, str] = field(default_factory=lambda: {
        'championship': 'Championship Game',
        'third_place': 'Third Place Game',
        'consolation': 'Consolation Game',
        'toilet_bowl': 'Toilet Bowl'
    })
    
    # Place names for final standings
    place_names: Dict[str, str] = field(default_factory=lambda: {
        'champion': 'Champion',
        'runner_up': 'Runner Up',
        'third_place': 'Third Place',
        'fourth_place': 'Fourth Place',
        'fifth_place': 'Fifth Place',
        'sixth_place': 'Sixth Place',
        'seventh_place': 'Seventh Place',
        'eighth_place': 'Eighth Place',
        'ninth_place': 'Ninth Place',
        'tenth_place': 'Tenth Place',
        'eleventh_place': 'Eleventh Place',
        'twelfth_place': 'Twelfth Place',
        '5th_place': 'Fifth Place',
        '6th_place': 'Sixth Place',
        '7th_place': 'Seventh Place',
        '8th_place': 'Eighth Place',
        '9th_place': 'Ninth Place',
        '10th_place': 'Tenth Place',
        '11th_place': 'Eleventh Place',
        '12th_place': 'Twelfth Place'
    })
    
    # First round playoff matchups (week 15)
    first_round_matchups: List[Dict[str, int]] = field(default_factory=lambda: [
        {'home': 1, 'away': 4},  # Winners bracket
        {'home': 2, 'away': 3},
        {'home': 5, 'away': 6},
        {'home': 7, 'away': 10},  # Consolation bracket
        {'home': 8, 'away': 9},
        {'home': 11, 'away': 12}
    ])
    
    @classmethod
    def get_config(cls, season: int) -> 'PlayoffConfig':
        """
        Get the playoff configuration for a given season.
        
        Args:
            season: The NFL season year
            
        Returns:
            PlayoffConfig instance for the season
        """
        if season <= 2012:
            # 2011-2012: 4-team winners bracket + 8-team consolation bracket
            return cls(
                regular_season_weeks=14,
                playoff_start_week=15,
                playoff_end_week=16,
                winners_bracket_size=4,
                consolation_bracket_size=8,
                has_middle_teams=False,
                has_divisions=False,
                has_byes=False,
                championship_week_games={
                    'championship': 'Championship Game',
                    'third_place': 'Third Place Game',
                    'consolation': 'Consolation Game',
                    'toilet_bowl': 'Toilet Bowl'
                },
                first_round_matchups=[
                    {'home': 1, 'away': 4},  # Winners bracket
                    {'home': 2, 'away': 3},
                    {'home': 5, 'away': 8},  # Consolation bracket
                    {'home': 6, 'away': 7},
                    {'home': 9, 'away': 12},
                    {'home': 10, 'away': 11}
                ]
            )
        elif season <= 2015:
            # 2013-2015: 4-team winners bracket (with divisions) + 4-team middle teams + 4-team consolation
            return cls(
                regular_season_weeks=14,
                playoff_start_week=15,
                playoff_end_week=16,
                winners_bracket_size=4,
                consolation_bracket_size=4,
                has_middle_teams=True,
                has_divisions=True,
                has_byes=False,
                championship_week_games={
                    'championship': 'Championship Game',
                    'third_place': 'Third Place Game',
                    'consolation': 'Consolation Game',
                    'toilet_bowl': 'Toilet Bowl'
                },
                first_round_matchups=[
                    {'home': 1, 'away': 4},  # Winners bracket
                    {'home': 2, 'away': 3},  # Middle teams play for sum of both weeks
                    {'home': 5, 'away': 8},  # Middle teams
                    {'home': 6, 'away': 7},
                    {'home': 9, 'away': 12},  # Consolation bracket
                    {'home': 10, 'away': 11}
                ]
            )
        elif season == 2017:
            # 2017: 10-team format with divisions - 4-team championship bracket + 2-team mediocre bowl + 4-team consolation
            return cls(
                regular_season_weeks=14,
                playoff_start_week=14,  # Playoffs start week 14
                playoff_end_week=16,
                winners_bracket_size=4,
                consolation_bracket_size=4,
                has_middle_teams=True,
                has_divisions=True,  # 2017 has divisions!
                has_byes=False,
                championship_week_games={
                    'championship': 'Championship Game',
                    'third_place': 'Third Place Game',
                    'mediocre_bowl': 'Mediocre Bowl',
                    'toilet_bowl': 'Toilet Bowl'
                },
                first_round_matchups=[
                    {'home': 1, 'away': 4},  # Winners bracket
                    {'home': 2, 'away': 3},
                    {'home': 5, 'away': 6},  # Mediocre bowl (2 teams)
                    {'home': 7, 'away': 10},  # Consolation bracket
                    {'home': 8, 'away': 9}
                ]
            )
        else:
            # 2016-2020: 6-team playoff with byes (quarterfinals, semifinals, championship)
            # 2021+: 17-week season with playoffs in weeks 15-17
            if season >= 2021:
                return cls(
                    regular_season_weeks=14,  # Regular season is Weeks 1-14, playoffs start Week 15
                    playoff_start_week=15,  # Playoffs start week 15
                    playoff_end_week=17,  # Playoffs end week 17
                    winners_bracket_size=6,
                    consolation_bracket_size=6,
                    has_middle_teams=False,
                    has_divisions=False,
                    has_byes=True,
                    championship_week_games={
                        'championship': 'Championship Game',
                        'third_place': 'Third Place Game',
                        'fifth_place': 'Fifth Place Game',
                        'toilet_bowl': 'Toilet Bowl'
                    },
                    first_round_matchups=[
                        {'home': 1, 'away': 4},  # Winners bracket (seeds 1,2 get byes)
                        {'home': 2, 'away': 3},
                        {'home': 5, 'away': 6},
                        {'home': 7, 'away': 10},  # Consolation bracket
                        {'home': 8, 'away': 9},
                        {'home': 11, 'away': 12}
                    ]
                )
            else:
                return cls(
                    regular_season_weeks=13,  # Regular season is Weeks 1-13, playoffs start Week 14
                    playoff_start_week=14,  # Playoffs start week 14 with quarterfinals
                    playoff_end_week=16,
                    winners_bracket_size=6,
                    consolation_bracket_size=6,
                    has_middle_teams=False,
                    has_divisions=False,
                    has_byes=True,
                    championship_week_games={
                        'championship': 'Championship Game',
                        'third_place': 'Third Place Game',
                        'fifth_place': 'Fifth Place Game',
                        'toilet_bowl': 'Toilet Bowl'
                    },
                    first_round_matchups=[
                        {'home': 1, 'away': 4},  # Winners bracket (seeds 1,2 get byes)
                        {'home': 2, 'away': 3},
                        {'home': 5, 'away': 6},
                        {'home': 7, 'away': 10},  # Consolation bracket
                        {'home': 8, 'away': 9},
                        {'home': 11, 'away': 12}
                    ]
                ) 