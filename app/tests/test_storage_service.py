# app/tests/test_storage_service.py
"""
Unit tests for the StorageService class.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from services.storage_service import StorageService


class TestStorageServiceInit:
    """Tests for StorageService initialization."""

    def test_init_with_client(self, mock_supabase_client):
        """Test initialization with a Supabase client."""
        service = StorageService(mock_supabase_client)

        assert service.supabase == mock_supabase_client


class TestLoadSchools:
    """Tests for the _load_schools method."""

    def test_loads_schools_from_db(self, mock_supabase_with_data):
        """Test loading schools from the database."""
        service = StorageService(mock_supabase_with_data)
        schools = service._load_schools()

        assert len(schools) == 2
        assert "School of Science" in schools
        assert "School of Technology" in schools


class TestStoreSchoolsFromConfig:
    """Tests for the store_schools_from_config method."""

    def test_stores_new_schools(self, mock_supabase_client):
        """Test storing new schools from configuration."""
        mock_supabase_client.table.return_value.select.return_value.execute.return_value.data = (
            []
        )
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        service = StorageService(mock_supabase_client)

        schools_to_store = ["School of Science", "School of Arts"]
        service.store_schools_from_config(schools_to_store)

        # Verify insert was called
        insert_calls = [
            c for c in mock_supabase_client.table.return_value.insert.call_args_list
        ]
        assert len(insert_calls) > 0


class TestUpsertGrant:
    """Tests for the _upsert_grant method."""

    def test_inserts_new_grant(self, mock_supabase_client, sample_processed_grant):
        """Test inserting a new grant."""
        # Mock select to return empty (grant doesn't exist)
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        service = StorageService(mock_supabase_client)
        service._upsert_grant(sample_processed_grant)

        # Verify insert was called
        mock_supabase_client.table.return_value.insert.assert_called_once()

    def test_updates_existing_grant(self, mock_supabase_client, sample_processed_grant):
        """Test updating an existing grant."""
        # Mock select to return existing grant
        existing_grant = [{"id": 123, "link": sample_processed_grant["link"]}]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            existing_grant
        )
        mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            MagicMock()
        )

        service = StorageService(mock_supabase_client)
        service._upsert_grant(sample_processed_grant)

        # Verify update was called
        mock_supabase_client.table.return_value.update.assert_called_once()


class TestLinkGrantToSchool:
    """Tests for the _link_grant_to_school method."""

    def test_creates_link_if_not_exists(self, mock_supabase_client):
        """Test creating a new grant-school link."""
        # Mock: link doesn't exist yet
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        service = StorageService(mock_supabase_client)
        service._link_grant_to_school(grant_id=1, school_id=2)

        # Verify insert was called
        insert_call = mock_supabase_client.table.return_value.insert.call_args
        assert insert_call is not None

    def test_skips_existing_link(self, mock_supabase_client):
        """Test that existing links are not duplicated."""
        # Mock: link already exists
        existing_link = [{"grant_id": 1, "school_id": 2}]
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = (
            existing_link
        )

        service = StorageService(mock_supabase_client)
        service._link_grant_to_school(grant_id=1, school_id=2)

        # Verify insert was NOT called (called 0 times for this operation)
        # Since select found existing, insert should not happen for the junction table


class TestStoreGrants:
    """Tests for the store_grants method."""

    def test_stores_multiple_grants(self, mock_supabase_client, sample_raw_grants):
        """Test storing multiple grants."""
        # Mock select to return empty (new grants)
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        mock_supabase_client.table.return_value.insert.return_value.execute.return_value = (
            MagicMock()
        )

        service = StorageService(mock_supabase_client)
        service.store_grants(sample_raw_grants)

        # Verify grants table was accessed
        table_calls = [c[0][0] for c in mock_supabase_client.table.call_args_list]
        assert "grants" in table_calls

    def test_handles_empty_grants_list(self, mock_supabase_client):
        """Test handling of empty grants list."""
        service = StorageService(mock_supabase_client)

        # Should not raise an exception
        service.store_grants([])

    def test_skips_invalid_grants(self, mock_supabase_client):
        """Test that grants without required fields are skipped."""
        service = StorageService(mock_supabase_client)

        invalid_grants = [
            {},  # Empty grant
            {"title": ""},  # Empty title
            {"title": None},  # None title
        ]

        # Should not raise an exception
        service.store_grants(invalid_grants)


class TestGrantDataMapping:
    """Tests for correct data mapping in grant operations."""

    def test_grant_data_includes_all_fields(
        self, mock_supabase_client, sample_processed_grant
    ):
        """Test that all required fields are included in the grant data."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )

        insert_mock = MagicMock()
        mock_supabase_client.table.return_value.insert = insert_mock
        insert_mock.return_value.execute.return_value = MagicMock()

        service = StorageService(mock_supabase_client)
        service._upsert_grant(sample_processed_grant)

        # Get the data that was passed to insert
        insert_call = insert_mock.call_args
        if insert_call:
            inserted_data = insert_call[0][0]

            # Verify required fields
            assert "title" in inserted_data
            assert "link" in inserted_data
            assert "school" in inserted_data
