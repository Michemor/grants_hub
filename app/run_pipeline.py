# app/run_pipeline.py
"""
Grant scraping pipeline that orchestrates scraping, filtering, and storage.
"""
import logging
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

from .config import get_settings
from .services.filter_service import FilterService
from .services.scraper_services import ScraperService
from .services.storage_service import StorageService

# Configure logging
logger = logging.getLogger(__name__)


def run_pipeline() -> int:
    """
    Execute the grant scraping pipeline.

    Pipeline steps:
    1. Scrape grants from search engines
    2. Filter and process grants
    3. Store results in database

    Returns:
        Number of grants successfully stored, or 0 if pipeline failed
    """
    # Load environment variables
    load_dotenv()

    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        return 0

    # Validate required API keys
    if not settings.serp_api:
        logger.error("SERP_API key not found in environment variables")
        return 0

    # Initialize services
    logger.info("Initializing pipeline services...")

    supabase_client = create_client(settings.supabase_url, settings.supabase_key)
    storage_service = StorageService(supabase_client=supabase_client)

    # Locate config file
    config_path = Path(__file__).resolve().parent / "configs" / "search_parameters.json"

    if not config_path.exists():
        logger.error(f"Search parameters config not found: {config_path}")
        return 0

    logger.info("Starting grant scraping pipeline...")

    # Step 1: Scrape data
    try:
        scraper_service = ScraperService(
            api_key=settings.serp_api, query_file=config_path
        )
        search_config = scraper_service.load_search_config()
        raw_grants = scraper_service.run()
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        return 0

    if not raw_grants:
        logger.warning("No grants were scraped. Exiting pipeline.")
        return 0

    # Step 2: Process/filter data
    logger.info(f"Processing {len(raw_grants)} scraped grants...")

    filter_service = FilterService(
        search_config=search_config,
        max_deadline_days=settings.max_deadline_days,
        relevance_threshold=settings.relevance_threshold,
        enable_debug_output=settings.debug,
    )
    cleaned_grants = filter_service.process_grants(raw_grants)

    if not cleaned_grants:
        logger.warning("No grants passed filtering. Nothing to store.")
        return 0

    # Step 3: Store data
    logger.info(f"Storing {len(cleaned_grants)} cleaned grants...")

    storage_service.store_schools_from_config(config_path)
    saved_count = storage_service.store_grants(cleaned_grants)

    logger.info(f"Pipeline completed successfully. Stored {saved_count} grants.")
    return saved_count


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_pipeline()
