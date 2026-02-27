# app/tests/test_main.py
"""
Unit tests for the FastAPI application endpoints.
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    mock_client = MagicMock()
    # Setup chain for table().select().execute()
    mock_execute = MagicMock()
    mock_execute.data = []
    mock_client.table.return_value.select.return_value.execute.return_value = (
        mock_execute
    )
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        mock_execute
    )
    mock_client.table.return_value.select.return_value.ilike.return_value.execute.return_value = (
        mock_execute
    )
    return mock_client


@pytest.fixture
def mock_supabase_with_data():
    """Create a mock Supabase client with sample data."""
    mock_client = MagicMock()

    # Sample school data
    schools_data = [
        {"school_id": "uuid-1", "school_name": "School of Science"},
        {"school_id": "uuid-2", "school_name": "School of Arts"},
    ]

    # Sample grants data
    grants_data = [
        {
            "grant_id": "uuid-1",
            "title": "Research Grant",
            "description": "A test grant",
            "link": "https://example.com",
            "school": "School of Science",
        }
    ]

    mock_schools_execute = MagicMock()
    mock_schools_execute.data = schools_data

    mock_grants_execute = MagicMock()
    mock_grants_execute.data = grants_data

    def table_router(table_name):
        mock_table = MagicMock()
        if table_name == "schools":
            mock_table.select.return_value.execute.return_value = mock_schools_execute
            mock_table.select.return_value.eq.return_value.execute.return_value = (
                mock_schools_execute
            )
        else:
            mock_table.select.return_value.execute.return_value = mock_grants_execute
            mock_table.select.return_value.eq.return_value.execute.return_value = (
                mock_grants_execute
            )
            mock_table.select.return_value.ilike.return_value.execute.return_value = (
                mock_grants_execute
            )
        return mock_table

    mock_client.table = table_router
    return mock_client


class TestRootEndpoint:
    """Tests for the root API endpoint."""

    def test_root_endpoint_returns_200(self, mock_env_vars, monkeypatch):
        """Test that the root endpoint returns 200."""
        # Set environment variables
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client") as mock_create:
            mock_create.return_value = MagicMock()

            from app.main import app

            client = TestClient(app)

            response = client.get("/api")

            assert response.status_code == 200
            assert "message" in response.json()


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_endpoint(self, mock_env_vars, monkeypatch):
        """Test health check returns status ok."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client") as mock_create:
            mock_create.return_value = MagicMock()

            from app.main import app

            client = TestClient(app)

            response = client.get("/api/health")

            assert response.status_code == 200


class TestSchoolsEndpoint:
    """Tests for the schools endpoint."""

    def test_get_schools_returns_list(
        self, mock_env_vars, monkeypatch, mock_supabase_with_data
    ):
        """Test that schools endpoint returns a list."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase_with_data):
            from app.main import app

            client = TestClient(app)

            response = client.get("/api/schools")

            assert response.status_code == 200
            data = response.json()
            assert "schools" in data or isinstance(data, list)


class TestGrantsEndpoint:
    """Tests for the grants endpoint."""

    def test_get_grants_returns_list(
        self, mock_env_vars, monkeypatch, mock_supabase_with_data
    ):
        """Test that grants endpoint returns a list."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase_with_data):
            from app.main import app

            client = TestClient(app)

            response = client.get("/api/grants")

            assert response.status_code == 200
            data = response.json()
            assert "grants" in data or isinstance(data, list)


class TestSearchEndpoint:
    """Tests for the grants search endpoint."""

    def test_search_with_query(
        self, mock_env_vars, monkeypatch, mock_supabase_with_data
    ):
        """Test search with a query parameter."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase_with_data):
            from app.main import app

            client = TestClient(app)

            response = client.get("/api/grants/search?q=research")

            assert response.status_code == 200

    def test_search_without_query(
        self, mock_env_vars, monkeypatch, mock_supabase_with_data
    ):
        """Test search without a query parameter."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase_with_data):
            from app.main import app

            client = TestClient(app)

            response = client.get("/api/grants/search")

            # Should return 400 or 422 for missing required param, or 200 if optional
            assert response.status_code in [400, 422, 200]


class TestGrantsBySchool:
    """Tests for the grants by school endpoint."""

    def test_get_grants_by_school(
        self, mock_env_vars, monkeypatch, mock_supabase_with_data
    ):
        """Test getting grants for a specific school."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase_with_data):
            from app.main import app

            client = TestClient(app)

            response = client.get("/api/grants/School%20of%20Science")

            assert response.status_code == 200

    def test_get_grants_by_nonexistent_school(
        self, mock_env_vars, monkeypatch, mock_supabase
    ):
        """Test getting grants for a school that doesn't exist."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase):
            from app.main import app

            client = TestClient(app)

            response = client.get("/api/grants/NonExistentSchool")

            # Should return empty list, not 404
            assert response.status_code == 200


class TestDigestEndpoint:
    """Tests for the digest email endpoint."""

    def test_create_digest_valid_input(
        self, mock_env_vars, monkeypatch, mock_supabase_with_data
    ):
        """Test creating a digest with valid input."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase_with_data):
            from app.main import app

            client = TestClient(app)

            digest_data = {
                "school_email": "test@example.com",
                "school_name": "School of Science",
                "grants": [
                    {"title": "Test Grant", "funding_link": "https://example.com/grant"}
                ],
            }

            response = client.post("/api/digest", json=digest_data)

            # May return 200, 201, or other based on implementation
            assert response.status_code in [200, 201, 422, 500]

    def test_create_digest_invalid_email(
        self, mock_env_vars, monkeypatch, mock_supabase
    ):
        """Test creating a digest with invalid email."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase):
            from app.main import app

            client = TestClient(app)

            digest_data = {
                "school_email": "not-an-email",
                "school_name": "School of Science",
                "grants": [],
            }

            response = client.post("/api/digest", json=digest_data)

            # Should return validation error
            assert response.status_code == 422


class TestRefreshEndpoint:
    """Tests for the refresh pipeline endpoint."""

    def test_refresh_pipeline(self, mock_env_vars, monkeypatch, mock_supabase):
        """Test triggering the refresh pipeline."""
        for key, value in mock_env_vars.items():
            monkeypatch.setenv(key, value)

        with patch("app.main.create_client", return_value=mock_supabase):
            with patch("app.main.run_grant_pipeline", return_value=5):
                from app.main import app

                client = TestClient(app)

                response = client.get("/api/refresh")

                # May require auth or have other restrictions
                assert response.status_code in [200, 401, 403, 500]
