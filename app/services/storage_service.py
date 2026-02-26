# app/services/storage_service.py
from typing import List, Dict, Any
from supabase import Client

class StorageService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.school_map = self._load_schools()
        
    def store_schools_from_config(self, config_path: str):
        """Reads school information from the JSON config and stores it in the database."""
        import json
        print("Storing school parameters to the database...")
        try:
            with open(config_path, "r") as f:
                search_config = json.load(f)
                
            for school_name, config in search_config.items():
                print(f"Processing school: {school_name}")
                # Upsert school configuration into the schools table
                school_data = {
                    "school_name": school_name,
                    # Optional mapping if your table has more columns, e.g. "school_description"
                    "school_description": config["queries"]
                }
                
                # Check if school already exists
                existing = self.supabase.table("schools").select("school_id").eq("school_name", school_name).execute()
                
                if existing.data and len(existing.data) > 0:
                    school_id = existing.data[0]["school_id"]
                    self.supabase.table("schools").update(school_data).eq("school_id", school_id).execute()
                else:
                    self.supabase.table("schools").insert(school_data).execute()
                    
            print("Successfully stored schools in the database.")
            # Reload school map to reflect changes
            self.school_map = self._load_schools()
            
        except Exception as e:
            print(f"Error storing schools: {e}")

    def _load_schools(self) -> Dict[str, str]:
        """Fetches all schools once to map their names to their IDs."""
        school_map = {}
        try:
            response = self.supabase.table("schools").select("school_id, school_name, school_description").execute()
            for school in response.data:
                # Store both the full name and abbreviation to make matching easy
                school_map[school["school_name"]] = school["school_id"]
                school_map[school["school_description"]] = school["school_id"]
        except Exception as e:
            print(f"Failed to load schools from Supabase: {e}")
            
        return school_map

    def store_grants(self, grants: List[Dict[str, Any]]):
        """Saves the grants and creates the links in the junction table."""
        print("Starting the storage engine...")
        saved_count = 0

        for grant in grants:
            try:
                # 1. Prepare the grant data
                grant_data = {
                    "title": grant.get("title"),
                    "description": grant.get("snippet", ""),
                    "link": grant.get("funding_link"),
                    "funder": grant.get("organization"),
                    "deadline": grant.get("deadline"),
                    "school": grant.get("school"),
                    "ai_confidence_score": grant.get("relevance_score", 0)
                }
                
                # 2. Save the grant and get its new ID
                # Check if it already exists to avoid missing unique constraint errors on upsert
                existing = self.supabase.table("grants").select("grant_id").eq("link", grant_data["link"]).execute()
                
                if existing.data and len(existing.data) > 0:
                    grant_id = existing.data[0]["grant_id"]
                    # Update existing
                    grant_response = self.supabase.table("grants").update(grant_data).eq("grant_id", grant_id).execute()
                else:
                    # Insert new
                    grant_response = self.supabase.table("grants").insert(grant_data).execute()
                    if grant_response.data and len(grant_response.data) > 0:
                        grant_id = grant_response.data[0].get("grant_id")
                    else:
                        continue
                
                # 3. Find the matching school ID
                school_name = grant.get("school", "Unknown")
                school_id = self.school_map.get(school_name)
                
                # 4. Save the connection in the junction table
                if school_id and grant_id:
                    link_data = {
                        "grant_id": grant_id,
                        "school_id": school_id
                    }
                    
                    # Check junction exactly to avoid missing unique constraint on junction table
                    existing_link = self.supabase.table("schools_grants").select("*").eq("grant_id", grant_id).eq("school_id", school_id).execute()
                    if not existing_link.data or len(existing_link.data) == 0:
                        self.supabase.table("schools_grants").insert(link_data).execute()
                    
                saved_count += 1
                
            except Exception as e:
                print(f"Error saving grant '{grant.get('title')}': {e}")

        print(f"Storage complete. Saved {saved_count} grants to Supabase.")
        return saved_count