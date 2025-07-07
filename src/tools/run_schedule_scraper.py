"""
Script to run the NFL schedule scraper.
"""

from ingest.nfl.schedule import NFLScheduleIngest

def main():
    print("\n=== NFL Schedule Scraper ===\n")
    scraper = NFLScheduleIngest()
    try:
        # Process the 2012 season with force_refresh=True
        scraper.fetch_and_process_season(2012, force_refresh=True)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        scraper.__del__()

if __name__ == "__main__":
    main() 