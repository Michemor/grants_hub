import serpapi
from datetime import datetime
import os
import re
from dotenv import load_dotenv
import json


load_dotenv()

class ScraperService:
        def __init__(self, api_key=None, query_file="configs/search_queries.json"):
           self.api_key = os.getenv("SERP_API") if api_key is None else api_key
           self.query_file = query_file
           self.search_config = self.load_search_config()

        def load_search_config(self):
              with open(self.query_file, "r") as f:
                  return json.load(f)
              
        def fetch_grants_from_query(self, query, result_limit, search_engine="google"):
            params = {
                "engine": search_engine,
                "q": query,
                "tbs": "qdr:m",  # Filter results from the past year
                "api_key": self.api_key,
                "num": result_limit
            }
            search = serpapi.GoogleSearch(params)
            results = search.get_dict()

            return results.get("organic_results", [])

        def run(self):
            all_grants = []
            scraped_at = datetime.now().isoformat()
            

            for school, config in self.search_config.items():
                queries = config.get("queries", [])
                result_limit = config.get("result_limit", 20)
                search_engine = config.get("engine", "google")

                for query in queries:
                    print(f"Scraping grants for {school} with query: '{query}'...")
                    grants = self.fetch_grants_from_query(query, result_limit, search_engine)

                for grant in grants:
                    title = grant.get("title", "No title available")
                    snippet = grant.get("snippet", "No snippet available")
                    funding_link = grant.get("link", "No link available")
                    organization = grant.get("source", "No source available")
                    source = grant.get("displayed_link", "No source available")
                    deadline_match = re.search(r'(?i)(deadline|closes|due date)[:\s]*([A-Za-z0-9\s,]+)', snippet)
                    deadline = deadline_match.group(2).strip() if deadline_match else "Check link for deadline"

                    all_grants.append({
                        "school": school,
                        "title": title,
                        "snippet": snippet,
                        "funding_link": funding_link,
                        "organization": organization,
                        "source": source,
                        "deadline": deadline,
                        "date_scraped": scraped_at
                    })
            return all_grants
             
              
       