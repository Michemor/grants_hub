import re
import hashlib
from datetime import datetime, timedelta
import time
from typing import List, Dict, Any, Optional
from dateutil import parser
import json
from google import genai
import os
from pathlib import Path

class FilterService:
    """
    Service to filter and process scraped grant data.
    This service applies various filters to ensure that the grants are relevant and up-to-date.
    """

    def __init__(self, search_config: Dict[str, Any] = None):
        self.search_config = search_config
        self.today = datetime.now()
        self.max_deadline = self.today + timedelta(days=365)
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def process_grants(self, raw_grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process and filter raw grants based on relevance and deadlines.
        """
        normalized_grants = self._normalize_grant(raw_grants)
        unique_grants = self._deduplicate_grants(normalized_grants)
        relevant_grants = self._filter_by_relevance(unique_grants)
        # classified_grants = self._ai_classify(relevant_grants)
        valid_grants = self._filter_by_deadline(relevant_grants)

        # for testing purposes to store the filtered grants in a json file
        current_dir = Path(__file__).resolve().parent
        config_path = current_dir.parent / "configs" / "filtered_grants.json"
        
        with open(config_path, "w") as f:
            json.dump(valid_grants, f, indent=4)
        return valid_grants

    def _normalize_grant(self, grants: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize grant data to ensure consistent formatting.
        """
        normalized_grants = []

        for grant in grants:
            normalized_grant = {
                "title": grant.get("title", "").strip(),
                "snippet": grant.get("snippet", "").strip(),
                "funding_link": grant.get("funding_link", "").strip(),
                "organization": grant.get("organization", "").strip(),
                "source": grant.get("source", "").strip(),
                "deadline": grant.get("deadline", "").strip(),
                "date_scraped": grant.get("date_scraped", "").strip(),
                "school": grant.get("school", "").strip(),
            }
            normalized_grants.append(normalized_grant)
        return normalized_grants

    def _ai_classify(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Classifies research grants using Gemini and attaches structured metadata."""

        print(f"Starting AI Classification for {len(grants)} grants...")

        for grant in grants:
            prompt = self._build_prompt(grant)

            try:
                # Use standard gemini-1.5-flash-8b model name
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2
                    )
                )

                metadata = json.loads(response.text)

                grant["ai_metadata"] = metadata
                grant["ai_confidence_score"] = metadata.get("confidence_score", 0.0)

            except Exception as e:
                print(f"AI classification failed for '{grant.get('title')}': {e}")

                grant["ai_metadata"] = None
                grant["ai_confidence_score"] = 0.0

            # Sleep 5 seconds between requests to strictly respect the Gemini free tier limit of 15 RPM.
            # (60 seconds / 15 requests = 4 seconds/request. We add 1 second padding for safety).
            time.sleep(5)  # Respect API limits

        return grants 
    
    def _deduplicate_grants(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate grants based on a hash of the title and funding link.
        """
        seen_hashes = set()
        unique_grants = []

        for grant in grants:
            identifier = self.__generate_grant_hash(grant)
            if identifier not in seen_hashes:
                seen_hashes.add(identifier)
                unique_grants.append(grant)

        return unique_grants
    
    def _filter_by_relevance(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter grants based on relevance to the specified schools and keywords.
        """
        relevant_grants = []

        for grant in grants:
            school = grant.get("school", "")
            config = self.search_config.get(school, {})
            priority = config.get("priority", [])
            exclude = config.get("exclude", [])

            text = f"{grant.get('title', '')} {grant.get('snippet', '')}".lower()
            score = 0

            score += sum(2 for word in priority if word.lower() in text)
            score -= sum(2 for word in exclude if word.lower() in text)
            
            grant["relevance_score"] = score

            if score >= 2:
                relevant_grants.append(grant)
        
        return relevant_grants
    
    def _filter_by_deadline(self, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters grants to ensure deadlines fall within the acceptable window."""
        valid_grants = []

        for grant in grants:
            text_body = f"{grant.get('title', '')} {grant.get('snippet', '')}"
            deadline = self.__extract_deadline(text_body)

            # Ensure deadline exists and falls between today and max_deadline
            if deadline and self.today <= deadline <= self.max_deadline:
                grant["deadline"] = deadline.isoformat()
                valid_grants.append(grant)
                
        return valid_grants

    def __generate_grant_hash(self, grant: Dict[str, Any]) -> str:
        """
        Generate a unique hash for a grant based on its title and funding link.
        """
        identifier = f"{grant.get('title', '').lower()}|{grant.get('funding_link', '').lower()}"
        return hashlib.sha256(identifier.encode("utf-8")).hexdigest()

    def __extract_deadline(self, text: str) -> Optional[datetime]:
        """Uses regex and dateutil to find and parse dates from text."""
        date_patterns = re.findall(
            r'\b(?:\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s?\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2},?\s\d{4}|\d{1,2}/\d{1,2}/\d{4})',
            text,
            re.IGNORECASE
        )

        for match in date_patterns:
            try:
                # fuzzy=True allows the parser to ignore surrounding text
                return parser.parse(match, fuzzy=True)
            except Exception:  
                continue

        return None
    
    def _build_prompt(self, grant: Dict[str, Any]) -> str:

        return (f"""
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
            """)