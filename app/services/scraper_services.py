# app/services/scraper_services.py
"""
Scraper service for fetching grant opportunities from search engines via SerpAPI.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import serpapi

# Configure module logger
logger = logging.getLogger(__name__)

# Compiled regex patterns for better performance
FUNDER_PATTERN = re.compile(
    r"\b([A-Z][a-zA-Z\&\-\']+(?:\s+(?:of|for|and|\&|the|in))?\s*"
    r"[A-Z][a-zA-Z\&\-\']*(?:\s+[A-Z][a-zA-Z\&\-\']+)*\s+"
    r"(?:Foundation|Institute|Institutes|Agency|Department|Council|Society|"
    r"Association|Charity|Trust|Fund|Endowment|Initiative|Center|Centre|"
    r"University|Program|Commission|Network|Organization))\b"
)

DEADLINE_KEYWORD_PATTERN = re.compile(
    r"(?i)(?:deadline|closes|due(?: date)?|applications due)[:\s\-]*([^\.]+)"
)

DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{1,2}[\s\-\/]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\/\,]+\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\/\.]+\d{1,2}[\,\s\-\/]+\d{2,4}|"
    r"\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4}"
    r")\b",
    re.IGNORECASE,
)

# Default values
DEFAULT_RESULT_LIMIT = 5
DEFAULT_SEARCH_ENGINE = "google"
DEFAULT_TIME_FILTER = "qdr:m"  # Past month


class ScraperService:
    """
    Service for scraping grant opportunities from search engines.

    Uses SerpAPI to fetch results from Google and other search engines
    based on configured queries for each school.
    """

    def __init__(self, api_key: str, query_file: str | Path):
        """
        Initialize the scraper service.

        Args:
            api_key: SerpAPI API key
            query_file: Path to search_parameters.json configuration file

        Raises:
            ValueError: If API key is not provided
            FileNotFoundError: If query file doesn't exist
        """
        if not api_key:
            raise ValueError("SerpAPI key is required")

        self.api_key = api_key
        self.query_file = Path(query_file)

        if not self.query_file.exists():
            raise FileNotFoundError(f"Query file not found: {self.query_file}")

        self.search_config = self.load_search_config()

    def load_search_config(self) -> Dict[str, Any]:
        """
        Load search configuration from JSON file.

        Returns:
            Dictionary mapping school names to their search configurations
        """
        with open(self.query_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def fetch_grants_from_query(
        self,
        query: str,
        result_limit: int = DEFAULT_RESULT_LIMIT,
        search_engine: str = DEFAULT_SEARCH_ENGINE,
    ) -> List[Dict[str, Any]]:
        """
        Fetch search results for a single query.

        Args:
            query: Search query string
            result_limit: Maximum number of results to return
            search_engine: Search engine to use (default: google)

        Returns:
            List of organic search results
        """
        logger.debug(f"Scraping results for query: '{query}'")

        params = {
            "engine": search_engine,
            "q": query,
            "tbs": DEFAULT_TIME_FILTER,
            "api_key": self.api_key,
            "num": result_limit,
        }

        try:
            search = serpapi.GoogleSearch(params)
            results = search.get_dict()

            if "error" in results:
                logger.error(f"SerpAPI error: {results['error']}")
                return []

            return results.get("organic_results", [])

        except Exception as e:
            logger.error(f"Error fetching results for query '{query}': {e}")
            return []

    def run(self) -> List[Dict[str, Any]]:
        """
        Run the scraper for all configured schools and queries.

        Returns:
            List of scraped grant dictionaries
        """
        all_grants: List[Dict[str, Any]] = []
        scraped_at = datetime.now().isoformat()

        total_queries = sum(
            len(config.get("queries", [])) for config in self.search_config.values()
        )
        logger.info(
            f"Starting scraper with {total_queries} queries across {len(self.search_config)} schools"
        )

        for school, config in self.search_config.items():
            queries = config.get("queries", [])
            result_limit = config.get("result_limit", DEFAULT_RESULT_LIMIT)
            search_engine = config.get("engine", DEFAULT_SEARCH_ENGINE)

            for query in queries:
                logger.info(f"Scraping grants for {school}: '{query}'")
                results = self.fetch_grants_from_query(
                    query, result_limit, search_engine
                )

                for result in results:
                    grant = self._parse_search_result(result, school, scraped_at)
                    all_grants.append(grant)

        logger.info(f"Scraping complete. Total grants found: {len(all_grants)}")
        return all_grants

    def _parse_search_result(
        self,
        result: Dict[str, Any],
        school: str,
        scraped_at: str,
    ) -> Dict[str, Any]:
        """
        Parse a single search result into a grant dictionary.

        Args:
            result: Raw search result from SerpAPI
            school: School name this result belongs to
            scraped_at: ISO timestamp of when scraping occurred

        Returns:
            Parsed grant dictionary
        """
        title = result.get("title", "No title available")
        snippet = result.get("snippet", "No snippet available")

        return {
            "title": title,
            "snippet": snippet,
            "funding_link": result.get("link", ""),
            "organization": self._extract_funder(
                title, snippet, result.get("source", "")
            ),
            "source": result.get("displayed_link", ""),
            "deadline": self._extract_deadline(snippet),
            "date_scraped": scraped_at
        }

    def _extract_funder(self, title: str, snippet: str, default: str) -> str:
        """
        Extract funding organization name from title or snippet.

        Args:
            title: Grant title
            snippet: Grant description snippet
            default: Default value if no funder found

        Returns:
            Extracted funder name or default
        """
        # Try snippet first, then title
        for text in (snippet, title):
            match = FUNDER_PATTERN.search(text)
            if match:
                return match.group(1).strip()
        return default or "Unknown"

    def _extract_deadline(self, text: str) -> str:
        """
        Extract deadline date from text.

        Args:
            text: Text to search for deadline

        Returns:
            Extracted deadline string or default message
        """
        # First try to find explicit deadline mention
        deadline_match = DEADLINE_KEYWORD_PATTERN.search(text)

        if deadline_match:
            extracted = deadline_match.group(1).strip()
            date_match = DATE_PATTERN.search(extracted)
            if date_match:
                return date_match.group(0).strip()
            # Return truncated text if no date pattern found
            return extracted[:25].strip() if len(extracted) > 25 else extracted

        # Fallback: look for any date in the text
        date_match = DATE_PATTERN.search(text)
        if date_match:
            return date_match.group(0).strip()

        return "Check link for deadline"
