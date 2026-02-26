from pathlib import Path
import hashlib
import serpapi
from datetime import datetime
import re
import json

class ScraperService:
        def __init__(self, api_key, query_file):
           self.api_key = api_key
           self.query_file = query_file
           self.search_config = self.load_search_config()
           self.cache_dir = Path(__file__).resolve().parent.parent / "cache"
           self.cache_dir.mkdir(exist_ok=True)

        def load_search_config(self):
              with open(self.query_file, "r") as f:
                  return json.load(f)
              
        def _get_cache_path(self, query):
            """Generates a cache file path based on the query string."""
            query_hash = hashlib.sha256(query.encode()).hexdigest()
            
            return self.cache_dir / f"{query_hash}.json"
        
        def _is_cache_valid(self, cache_path: Path, max_age_hours: int = 24) -> bool:
            """Check if cache exists and is less than max_age_hours old."""
            if not cache_path.exists():
                return False

            cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
            return cache_age < (max_age_hours * 3600)


              
        def fetch_grants_from_query(self, query, result_limit, search_engine="google"):

            cache_path = self._get_cache_path(query)
            if self._is_cache_valid(cache_path):
                print(f"Using cached results for query: '{query}'")
                with open(cache_path, "r") as f:
                    return json.load(f)
                
            print(f"Scraping new results for query: '{query}'")
            params = {
                "engine": search_engine,
                "q": query,
                "tbs": "qdr:m",  # Filter results from the past month
                "api_key": self.api_key,
                "num": result_limit
            }
            search = serpapi.GoogleSearch(params)
            results = search.get_dict()
            organized_results = results.get("organic_results", [])

            with open(cache_path, "w") as f:
                json.dump(organized_results, f)
            
            return organized_results

        def run(self):
            all_grants = []
            scraped_at = datetime.now().isoformat()
            

            for school, config in self.search_config.items():
                queries = config.get("queries", [])
                result_limit = config.get("result_limit", 5)
                search_engine = config.get("engine", "google")

                for query in queries:
                    print(f"Scraping grants for {school} with query: '{query}'...")
                    grants = self.fetch_grants_from_query(query, result_limit, search_engine)

                    for grant in grants:
                        title = grant.get("title", "No title available")
                        snippet = grant.get("snippet", "No snippet available")
                        funding_link = grant.get("link", "No link available")
                        funder_info = grant.get("source", "No source available")
                        
                        funder_pattern = r'\b([A-Z][a-zA-Z\&\-\']+(?:\s+(?:of|for|and|\&|the|in))?\s*[A-Z][a-zA-Z\&\-\']*(?:\s+[A-Z][a-zA-Z\&\-\']+)*\s+(?:Foundation|Institute|Institutes|Agency|Department|Council|Society|Association|Charity|Trust|Fund|Endowment|Initiative|Center|Centre|University|Program|Commission|Network|Organization))\b'
                        funder_match = re.search(funder_pattern, snippet)
                        if funder_match:
                            funder_info = funder_match.group(1).strip()
                        else:
                            funder_match_title = re.search(funder_pattern, title)
                            if funder_match_title:
                                funder_info = funder_match_title.group(1).strip()
                                
                        organization = funder_info
                        source = grant.get("displayed_link", "No source available")
                        
                        deadline = "Check link for deadline"
                        deadline_match = re.search(r'(?i)(?:deadline|closes|due(?: date)?|applications due)[:\s\-]*([^\.]+)', snippet)
                        date_pattern = r'\b(?:\d{1,2}[\s\-\/]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\/\,]+\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-\/\.]+\d{1,2}[\,\s\-\/]+\d{2,4}|\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})\b'
                        
                        if deadline_match:
                            extracted_text = deadline_match.group(1).strip()
                            date_match = re.search(date_pattern, extracted_text, re.IGNORECASE)
                            if date_match:
                                deadline = date_match.group(0).strip()
                            else:
                                deadline = extracted_text[:25].strip()
                        else:
                            date_match = re.search(date_pattern, snippet, re.IGNORECASE)
                            if date_match:
                                deadline = date_match.group(0).strip()
    
                        all_grants.append({
                            "title": title,
                            "snippet": snippet,
                            "funding_link": funding_link,
                            "organization": organization,
                            "source": source,
                            "deadline": deadline,
                            "date_scraped": scraped_at,
                            "school": school
                        })
            return all_grants
             
              
       