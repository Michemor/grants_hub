import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from .services.scraper_services import ScraperService
from .services.filter_service import FilterService
from .services.storage_service import StorageService

def run_pipeline(use_cache: bool = False):
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("SERP_API")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    # Initialize services
    supabase_client = create_client(supabase_url, supabase_key)
    storage_service = StorageService(supabase_client=supabase_client)
    
    current_file = Path(__file__).resolve().parent
    app_dir =  current_file / "configs" / "search_parameters.json"

    print("Starting grant scraping pipeline...")
    
    # Scrape data
    scraper_service = ScraperService(api_key=api_key, query_file=app_dir)

    if use_cache:
        # Uses cache
        scraper_service.cache_max_age_hours = float('inf')
        print("Running pipeline with caching enabled.")

    search_config = scraper_service.load_search_config()
    raw_grants = scraper_service.run()

    if not raw_grants:
        print("No grants were scraped. Exiting pipeline.")
        return
    
    # Processing data
    print(f"Initializing filter service. Processing {len(raw_grants)} grants..")
    filter_service = FilterService(search_config=search_config)
    cleaned_grants = filter_service.process_grants(raw_grants)

    # Store data
    print(f"Storing {len(cleaned_grants)} cleaned grants into the database...")
    storage_service.store_schools_from_config(app_dir)
    storage_service.store_grants(cleaned_grants)

    print("Pipeline execution completed successfully.")