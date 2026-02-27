# app/services/storage_service.py
"""
Storage service for persisting grants and schools to Supabase.
"""
import json
import logging
from typing import List, Dict, Any
from pathlib import Path

from supabase import Client

# Configure module logger
logger = logging.getLogger(__name__)


class StorageService:
    """
    Service for storing grants and school data in Supabase.

    Manages the grants, schools, and schools_grants junction tables.
    """

    def __init__(self, supabase_client: Client):
        """
        Initialize the storage service.

        Args:
            supabase_client: Initialized Supabase client
        """
        self.supabase = supabase_client
        self.school_map = self._load_schools()

    def store_schools_from_config(self, config_path: str | Path) -> int:
        """
        Read school information from JSON config and store in database.

        Args:
            config_path: Path to the search_parameters.json config file

        Returns:
            Number of schools processed
        """
        logger.info("Storing school parameters to the database...")
        processed_count = 0

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                search_config = json.load(f)

            for school_name, config in search_config.items():
                logger.debug(f"Processing school: {school_name}")

                # Store queries as JSON string if it's a list, otherwise use as-is
                queries = config.get("queries", [])
                description = (
                    json.dumps(queries) if isinstance(queries, list) else str(queries)
                )

                school_data = {
                    "school_name": school_name,
                    "school_description": description,
                }

                # Check if school already exists
                existing = (
                    self.supabase.table("schools")
                    .select("school_id")
                    .eq("school_name", school_name)
                    .execute()
                )

                if existing.data:
                    school_id = existing.data[0]["school_id"]
                    self.supabase.table("schools").update(school_data).eq(
                        "school_id", school_id
                    ).execute()
                else:
                    self.supabase.table("schools").insert(school_data).execute()

                processed_count += 1

            logger.info(
                f"Successfully stored {processed_count} schools in the database."
            )

            # Reload school map to reflect changes
            self.school_map = self._load_schools()

        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
        except Exception as e:
            logger.error(f"Error storing schools: {e}", exc_info=True)

        return processed_count

    def _load_schools(self) -> Dict[str, int]:
        """
        Fetch all schools to build a name-to-ID mapping.

        Returns:
            Dictionary mapping school names to their IDs
        """
        school_map: Dict[str, int] = {}
        try:
            response = (
                self.supabase.table("schools")
                .select("school_id, school_name")
                .execute()
            )
            for school in response.data or []:
                school_map[school["school_name"]] = school["school_id"]

            logger.debug(f"Loaded {len(school_map)} schools from database")
        except Exception as e:
            logger.error(f"Failed to load schools from Supabase: {e}", exc_info=True)

        return school_map

    def store_grants(self, grants: List[Dict[str, Any]]) -> int:
        """
        Save grants and create links in the junction table.

        Args:
            grants: List of processed grant dictionaries

        Returns:
            Number of grants successfully saved
        """
        logger.info(f"Starting storage of {len(grants)} grants...")
        saved_count = 0
        error_count = 0

        for grant in grants:
            try:
                grant_id = self._upsert_grant(grant)
                if grant_id is None:
                    error_count += 1
                    continue

                # Link grant to school via junction table
                school_name = grant.get("school", "")
                school_id = self.school_map.get(school_name)

                if school_id:
                    self._link_grant_to_school(grant_id, school_id)
                else:
                    logger.warning(
                        f"School not found: '{school_name}' for grant '{grant.get('title', '')[:50]}'"
                    )

                saved_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Error saving grant '{grant.get('title', '')[:50]}': {e}")

        logger.info(f"Storage complete. Saved: {saved_count}, Errors: {error_count}")
        return saved_count

    def _upsert_grant(self, grant: Dict[str, Any]) -> int | None:
        """
        Insert or update a grant in the database.

        Args:
            grant: Grant dictionary with processed data

        Returns:
            The grant_id if successful, None otherwise
        """
        grant_data = {
            "title": grant.get("title", "")[:500],  # Ensure max length
            "description": grant.get("snippet", "")[:2000],
            "link": grant.get("funding_link", ""),
            "funder": grant.get("organization", ""),
            "deadline": grant.get("deadline"),
            "school": grant.get("school", ""),  # Keep school column for direct queries
            "ai_confidence_score": grant.get("relevance_score", 0),
        }

        funding_link = grant_data["link"]
        if not funding_link:
            logger.warning(f"Grant missing funding link: {grant.get('title', '')[:50]}")
            return None

        # Check if grant already exists
        existing = (
            self.supabase.table("grants")
            .select("grant_id")
            .eq("link", funding_link)
            .execute()
        )

        if existing.data:
            # Update existing grant
            grant_id = existing.data[0]["grant_id"]
            self.supabase.table("grants").update(grant_data).eq(
                "grant_id", grant_id
            ).execute()
            return grant_id
        else:
            # Insert new grant
            response = self.supabase.table("grants").insert(grant_data).execute()
            if response.data:
                return response.data[0].get("grant_id")

            logger.warning(f"Failed to insert grant: {grant.get('title', '')[:50]}")
            return None

    def _link_grant_to_school(self, grant_id: int, school_id: int) -> None:
        """
        Create a link between a grant and school in the junction table.

        Args:
            grant_id: The grant's database ID
            school_id: The school's database ID
        """
        # Check if link already exists
        existing_link = (
            self.supabase.table("schools_grants")
            .select("grant_id")
            .eq("grant_id", grant_id)
            .eq("school_id", school_id)
            .execute()
        )

        if not existing_link.data:
            link_data = {"grant_id": grant_id, "school_id": school_id}
            self.supabase.table("schools_grants").insert(link_data).execute()
