# app/services/storage_service.py
from typing import List, Dict, Any
from supabase import Client

class StorageService:
    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client
        self.school_map = self._load_schools()

    def _load_schools(self) -> Dict[str, str]:
        """Fetches all schools once to map their names to their IDs."""
        school_map = {}
        try:
            response = self.supabase.table("schools").select("school_id, school_name, description").execute()
            for school in response.data:
                # Store both the full name and abbreviation to make matching easy
                school_map[school["school_name"]] = school["school_id"]
                school_map[school["description"]] = school["school_id"]
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
                    "deadline": grant.get("deadline"),
                    "ai_confidence_score": grant.get("relevance_score", 0),
                    "schools": grant.get("schools", [])
                }
                
                # 2. Save the grant and get its new ID
                # on_conflict="funding_link" prevents duplicates
                grant_response = self.supabase.table("grants").upsert(
                    grant_data, 
                    on_conflict="funding_link"
                ).execute()
                
                if not grant_response.data:
                    continue
                    
                grant_id = grant_response.data[0]["id"]
                
                # 3. Find the matching school ID
                school_name = grant.get("school", "Unknown")
                school_id = self.school_map.get(school_name)
                
                # 4. Save the connection in the junction table
                if school_id:
                    link_data = {
                        "grant_id": grant_id,
                        "school_id": school_id
                    }
                    self.supabase.table("grants_schools").upsert(
                        link_data, 
                        on_conflict="grant_id, school_id"
                    ).execute()
                    
                saved_count += 1
                
            except Exception as e:
                print(f"Error saving grant '{grant.get('title')}': {e}")

        print(f"Storage complete. Saved {saved_count} grants to Supabase.")
        return saved_count