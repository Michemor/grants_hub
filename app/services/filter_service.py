import re
import hashlib
from datetime import datetime, timedelta
from dateutil import parser

class FilterService:
    def __init__(self, search_config):
        self.search_config = search_config
        self.today = datetime.now()
        self.max_deadline = self.today + timedelta(days=7)  # Only consider grants with deadlines within the next week

    # check deduplication of grants
    def deduplication(self, grants):
        seen = set()
        unique_grants = []

        for grant in grants:
            identifier = self.__generate_hash(grant["title"], grant["funding_link"])
            if identifier not in seen:
                seen.add(identifier)
                unique_grants.append(grant)

        return unique_grants

    def __generate_hash(self, grant):
        base_string = (grant.get("title", "") + grant.get("funding_link", "")).lower()
        return hashlib.md5(base_string.encode()).hexdigest()
    

      # Extract and filter grants based on deadlines
    def extract_deadline(self, text):
        date_patterns = re.findall(
            r'\b(?:\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s?\d{4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{1,2},?\s\d{4}|\d{1,2}/\d{1,2}/\d{4})',
            text,
            re.IGNORECASE
        )

        for match in date_patterns:
            try:
                return parser.parse(match, fuzzy=True)
            except Exception:  
                continue

        return None

    def filter_by_deadline(self, grants):
        valid = []

        for grant in grants:
            combined_text = grant.get("title", "") + " " + grant.get("snippet", "")
            deadline = self.extract_deadline(combined_text)

            if deadline and self.today <= deadline <= self.max_deadline:
                grant["deadline"] = deadline.isoformat()
                valid.append(grant)
        return valid
    
    # Keyword relevance scoring

    def relevance_score(self, grants):
        filtered = []

        for grant in grants:
            school = grant.get("school", "")
            config = self.search_config.get(school, {})
            priority = config.get("priority_keywords", [])
            exclude = config.get("exclude_keywords", [])

            text = (grant.get("title", "") + " " + grant.get("snippet", "")).lower()

            score = 0 

            for word in priority:
                if word.lower() in text:
                    score += 2
            
            for word in exclude:
                if word.lower() in text:
                    score -= 2
            
            grant["relevance_score"] = score

            if score >= 2:
                filtered.append(grant)
        
        return filtered
    

    # combine all filters
    def process_grants(self, grants):
        grants = self.deduplication(grants)
        grants = self.filter_by_deadline(grants)
        grants = self.relevance_score(grants)

        return grants
