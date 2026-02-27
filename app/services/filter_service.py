import re
import hashlib
import logging
import time
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path

from dateutil import parser

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_DEADLINE_DAYS = 365
DEFAULT_RELEVANCE_THRESHOLD = 2
AI_RATE_LIMIT_SECONDS = 5
PRIORITY_WEIGHT = 2
EXCLUDE_WEIGHT = 2


class FilterService:
    """
    Service to filter and process scraped grant data.

    This service applies various filters to ensure that the grants
    are relevant and up-to-date.
    """

    def __init__(
        self,
        search_config: Dict[str, Any] | None = None,
        max_deadline_days: int = DEFAULT_MAX_DEADLINE_DAYS,
        relevance_threshold: int = DEFAULT_RELEVANCE_THRESHOLD,
        enable_debug_output: bool = False,
    ):
        """
        Initialize the FilterService.

        Args:
            search_config: Dictionary mapping school names to their config
            max_deadline_days: Maximum days ahead for valid deadlines
            relevance_threshold: Minimum score for a grant to be considered relevant
            enable_debug_output: Whether to write debug JSON files
        """
        self.search_config = search_config or {}
        self.max_deadline_days = max_deadline_days
        self.relevance_threshold = relevance_threshold
        self.enable_debug_output = enable_debug_output
        self._genai_client = None  # Lazy initialization

    @property
    def _today(self) -> datetime:
        """Get current date (computed fresh each time for long-running processes)."""
        return datetime.now()

    @property
    def _max_deadline(self) -> datetime:
        """Get maximum acceptable deadline date."""
        return self._today + timedelta(days=self.max_deadline_days)

    @property
    def genai_client(self):
        """Lazy-initialize the Gemini AI client only when needed."""
        if self._genai_client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError(
                    "GEMINI_API_KEY environment variable is required for AI classification"
                )
            from google import genai

            self._genai_client = genai.Client(api_key=api_key)
        return self._genai_client

    def process_grants(self, raw_grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and filter raw grants based on relevance and deadlines.

        Pipeline steps:
        1. Normalize grant data format
        2. Remove duplicates
        3. Filter by relevance score
        4. (Optional) AI classification
        5. Filter by deadline validity

        Args:
            raw_grants: List of raw grant dictionaries from scraper

        Returns:
            List of filtered, valid grant dictionaries
        """
        logger.info(f"Starting grant processing pipeline with {len(raw_grants)} grants")

        normalized_grants = self._normalize_grants(raw_grants)
        logger.debug(f"Normalized {len(normalized_grants)} grants")

        unique_grants = self._deduplicate_grants(normalized_grants)
        logger.info(f"Deduplicated to {len(unique_grants)} unique grants")

        relevant_grants = self._filter_by_relevance(unique_grants)
        logger.info(f"Filtered to {len(relevant_grants)} relevant grants")

        # AI classification is disabled by default (uncomment to enable)
        # relevant_grants = self._ai_classify(relevant_grants)

        valid_grants = self._filter_by_deadline(relevant_grants)
        logger.info(f"Final result: {len(valid_grants)} grants with valid deadlines")

        # Debug output (only if enabled)
        if self.enable_debug_output:
            self._write_debug_output(valid_grants)

        return valid_grants

    def _write_debug_output(self, grants: List[Dict[str, Any]]) -> None:
        """Write grants to JSON file for debugging purposes."""
        try:
            output_path = (
                Path(__file__).resolve().parent.parent
                / "configs"
                / "filtered_grants.json"
            )
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(grants, f, indent=4, default=str)
            logger.debug(f"Debug output written to {output_path}")
        except IOError as e:
            logger.warning(f"Failed to write debug output: {e}")

    def _normalize_grants(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize grant data to ensure consistent formatting.

        Args:
            grants: List of raw grant dictionaries

        Returns:
            List of normalized grant dictionaries with stripped strings
        """
        normalized_grants = []
        required_fields = [
            "title",
            "snippet",
            "funding_link",
            "organization",
            "source",
            "deadline",
            "date_scraped",
            "school",
        ]

        for grant in grants:
            normalized_grant = {
                field: str(grant.get(field, "")).strip() for field in required_fields
            }
            normalized_grants.append(normalized_grant)

        return normalized_grants

    def _ai_classify(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Classify research grants using Gemini AI and attach structured metadata.

        Args:
            grants: List of grant dictionaries to classify

        Returns:
            List of grants with ai_metadata and ai_confidence_score added
        """
        from google import genai as genai_module

        logger.info(f"Starting AI classification for {len(grants)} grants...")

        for i, grant in enumerate(grants, 1):
            prompt = self._build_prompt(grant)

            try:
                response = self.genai_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=genai_module.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )

                metadata = json.loads(response.text)
                grant["ai_metadata"] = metadata
                grant["ai_confidence_score"] = metadata.get("confidence_score", 0.0)
                logger.debug(
                    f"Classified grant {i}/{len(grants)}: {grant.get('title', '')[:50]}"
                )

            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse AI response for '{grant.get('title')}': {e}"
                )
                grant["ai_metadata"] = None
                grant["ai_confidence_score"] = 0.0
            except Exception as e:
                logger.error(
                    f"AI classification failed for '{grant.get('title')}': {e}"
                )
                grant["ai_metadata"] = None
                grant["ai_confidence_score"] = 0.0

            # Rate limiting: 15 RPM on free tier (4s/request + 1s padding)
            time.sleep(AI_RATE_LIMIT_SECONDS)

        logger.info("AI classification completed")
        return grants

    def _deduplicate_grants(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate grants based on a hash of the title and funding link.

        Args:
            grants: List of grant dictionaries

        Returns:
            List of unique grants (duplicates removed)
        """
        seen_hashes: set[str] = set()
        unique_grants = []

        for grant in grants:
            grant_hash = self._generate_grant_hash(grant)
            if grant_hash not in seen_hashes:
                seen_hashes.add(grant_hash)
                unique_grants.append(grant)

        return unique_grants

    def _filter_by_relevance(
        self, grants: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter grants based on relevance to the specified schools and keywords.

        Scoring:
        - +2 points for each priority keyword found
        - -2 points for each exclude keyword found
        - Grants must meet relevance_threshold to be included

        Args:
            grants: List of grant dictionaries

        Returns:
            List of grants that meet the relevance threshold
        """
        relevant_grants = []

        for grant in grants:
            school = grant.get("school", "")
            config = self.search_config.get(school, {})
            priority_keywords = config.get("priority", [])
            exclude_keywords = config.get("exclude", [])

            # Combine title and snippet for keyword matching
            searchable_text = (
                f"{grant.get('title', '')} {grant.get('snippet', '')}".lower()
            )

            # Calculate relevance score
            priority_score = sum(
                PRIORITY_WEIGHT
                for word in priority_keywords
                if word.lower() in searchable_text
            )
            exclude_penalty = sum(
                EXCLUDE_WEIGHT
                for word in exclude_keywords
                if word.lower() in searchable_text
            )

            score = priority_score - exclude_penalty
            grant["relevance_score"] = score

            if score >= self.relevance_threshold:
                relevant_grants.append(grant)

        return relevant_grants

    def _filter_by_deadline(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter grants to ensure deadlines fall within the acceptable window.

        Only includes grants with deadlines between today and max_deadline_days ahead.

        Args:
            grants: List of grant dictionaries

        Returns:
            List of grants with valid deadlines (deadline field updated to ISO format)
        """
        valid_grants = []
        today = self._today
        max_deadline = self._max_deadline

        for grant in grants:
            text_body = f"{grant.get('title', '')} {grant.get('snippet', '')}"
            deadline = self._extract_deadline(text_body)

            if deadline and today <= deadline <= max_deadline:
                grant["deadline"] = deadline.isoformat()
                valid_grants.append(grant)
            else:
                logger.debug(
                    f"Excluded grant (invalid deadline): {grant.get('title', '')[:50]}"
                )

        return valid_grants

    def _generate_grant_hash(self, grant: Dict[str, Any]) -> str:
        """
        Generate a unique hash for a grant based on its title and funding link.

        Args:
            grant: Grant dictionary

        Returns:
            SHA-256 hash string
        """
        identifier = (
            f"{grant.get('title', '').lower()}|{grant.get('funding_link', '').lower()}"
        )
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def _extract_deadline(self, text: str) -> Optional[datetime]:
        """
        Extract and parse deadline dates from text using regex patterns.

        Supports formats:
        - "15 Jan 2026", "January 15, 2026"
        - "01/15/2026", "15/01/2026"

        Args:
            text: Text to search for dates

        Returns:
            Parsed datetime or None if no valid date found
        """
        date_pattern = (
            r"\b(?:"
            r"\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s?\d{4}|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2},?\s\d{4}|"
            r"\d{1,2}/\d{1,2}/\d{4}"
            r")\b"
        )

        matches = re.findall(date_pattern, text, re.IGNORECASE)

        for match in matches:
            try:
                return parser.parse(match, fuzzy=True)
            except (ValueError, parser.ParserError):
                continue

        return None

    def _build_prompt(self, grant: Dict[str, Any]) -> str:

        return f"""
            You are an AI system that structures research grant opportunities 
            for a Research Grant Intelligence Platform.
            
            Analyze the grant below and extract structured metadata.
            
            Return ONLY valid JSON in this exact format:
            
            {{
              "research_domain": string,
              "subdomains": [string],
              "funding_type": string,
              "academic_level": [string],
              "eligible_entities": [string],
              "geographic_scope": string,
              "funding_amount": string,
              "has_deadline": boolean,
              "is_research_grant": boolean,
              "confidence_score": float
            }}
            
            Rules:
            - research_domain: High-level field (e.g., AI, Public Health, Climate Science, Agriculture, Education, Economics, Engineering, Social Sciences, Energy, etc.)
            - subdomains: More specific focus areas.
            - funding_type: One of ["Grant", "Fellowship", "Scholarship", "Research Contract", "Call for Proposal", "Prize", "Other"]
            - academic_level: ["Undergraduate", "Masters", "PhD", "Postdoc", "Faculty", "Institutional"]
            - eligible_entities: ["Individual Researcher", "University", "NGO", "Startup", "SME", "Government", "Consortium"]
            - geographic_scope: e.g., "Global", "Africa", "Kenya", "Europe"
            - has_deadline: true if a deadline is clearly stated
            - is_research_grant: true only if this is genuinely research-focused funding
            - confidence_score: 0.0–1.0 based on classification certainty
            
            If uncertain, make the best reasonable inference.
            Do not include explanations.
            Return JSON only.
            
            Grant Data:
            Title: {grant.get('title')}
            Description: {grant.get('snippet')}
            """
