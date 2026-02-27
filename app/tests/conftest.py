# app/tests/conftest.py
"""
Pytest fixtures and configuration for the grants intelligence hub tests.
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Add app directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============== Sample Data Fixtures ==============


@pytest.fixture
def sample_raw_grant():
    """Single raw grant as returned from scraper."""
    return {
        "title": "Clean Energy Research Grant 2026",
        "snippet": "Funding for solar and renewable energy projects. Deadline: 25 Oct 2026. Apply now.",
        "funding_link": "https://example.com/solar-grant",
        "organization": "National Science Foundation",
        "source": "nsf.gov",
        "deadline": "25 Oct 2026",
        "date_scraped": datetime.now().isoformat(),
        "school": "School of Science",
    }


@pytest.fixture
def sample_raw_grants():
    """Multiple raw grants for batch testing."""
    return [
        {
            "title": "AI Research Fellowship 2026",
            "snippet": "Grant funding for artificial intelligence research. Deadline: March 15, 2027",
            "funding_link": "https://example.com/ai-fellowship",
            "organization": "Google Research Foundation",
            "source": "google.com",
            "deadline": "March 15, 2027",
            "date_scraped": "2026-02-26T10:00:00",
            "school": "School of Technology",
        },
        {
            "title": "Climate Science Grant",
            "snippet": "Research funding for climate studies. Due date: 01/15/2027",
            "funding_link": "https://example.com/climate",
            "organization": "Environmental Agency",
            "source": "epa.gov",
            "deadline": "01/15/2027",
            "date_scraped": "2026-02-26T10:00:00",
            "school": "School of Science",
        },
        {
            "title": "Duplicate Grant",  # Same link as first
            "snippet": "This is a duplicate entry",
            "funding_link": "https://example.com/ai-fellowship",
            "organization": "Unknown",
            "source": "example.com",
            "deadline": "Check link",
            "date_scraped": "2026-02-26T10:00:00",
            "school": "School of Technology",
        },
    ]


@pytest.fixture
def sample_search_config():
    """Sample search configuration for testing."""
    return {
        "School of Technology": {
            "search_engine": "google",
            "result_limit": 5,
            "queries": ["AI research grant 2026"],
            "priority": [
                "grant",
                "funding",
                "research",
                "AI",
                "artificial intelligence",
            ],
            "exclude": ["news", "blog", "recap"],
        },
        "School of Science": {
            "search_engine": "google",
            "result_limit": 5,
            "queries": ["climate research funding"],
            "priority": ["grant", "funding", "research", "climate"],
            "exclude": ["news", "blog"],
        },
    }


@pytest.fixture
def sample_processed_grant():
    """Grant after processing/filtering."""
    return {
        "title": "AI Research Fellowship 2026",
        "snippet": "Grant funding for artificial intelligence research.",
        "funding_link": "https://example.com/ai-fellowship",
        "organization": "Google Research Foundation",
        "source": "google.com",
        "deadline": "2027-03-15T00:00:00",
        "date_scraped": "2026-02-26T10:00:00",
        "school": "School of Technology",
        "relevance_score": 6,
    }


# ============== Mock Fixtures ==============


@pytest.fixture
def mock_supabase_client():
    """
    Create a fully mocked Supabase client.

    This mock supports the method chaining pattern used by Supabase.
    """
    mock_client = MagicMock()

    # Create chainable mock for table operations
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_insert = MagicMock()
    mock_update = MagicMock()
    mock_eq = MagicMock()
    mock_in = MagicMock()
    mock_ilike = MagicMock()
    mock_limit = MagicMock()
    mock_execute = MagicMock()

    # Set up the chain
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_table.insert.return_value = mock_insert
    mock_table.update.return_value = mock_update

    mock_select.eq.return_value = mock_eq
    mock_select.in_.return_value = mock_in
    mock_select.ilike.return_value = mock_ilike
    mock_select.limit.return_value = mock_limit
    mock_select.execute.return_value = mock_execute

    mock_eq.eq.return_value = mock_eq
    mock_eq.execute.return_value = mock_execute
    mock_in.execute.return_value = mock_execute
    mock_ilike.execute.return_value = mock_execute
    mock_limit.execute.return_value = mock_execute
    mock_insert.execute.return_value = mock_execute
    mock_update.eq.return_value = mock_update
    mock_update.execute.return_value = mock_execute

    # Default empty response
    mock_execute.data = []

    return mock_client


@pytest.fixture
def mock_supabase_with_data(mock_supabase_client):
    """Supabase client that returns sample data."""
    # Configure to return sample grants
    mock_supabase_client.table.return_value.select.return_value.execute.return_value.data = [
        {
            "grant_id": 1,
            "title": "Test Grant",
            "description": "Test description",
            "link": "https://example.com/test",
            "funder": "Test Foundation",
            "deadline": "2027-01-01",
            "school": "School of Technology",
            "ai_confidence_score": 5,
        }
    ]
    return mock_supabase_client


@pytest.fixture
def mock_serpapi_response():
    """Sample SerpAPI response."""
    return {
        "organic_results": [
            {
                "title": "Research Grant Opportunity",
                "snippet": "Apply for our research funding program. Deadline: December 31, 2026",
                "link": "https://example.com/grant1",
                "source": "foundation.org",
                "displayed_link": "foundation.org/grants",
            },
            {
                "title": "Fellowship Program - National Institute",
                "snippet": "Fellowship for graduate students. Applications due January 15, 2027",
                "link": "https://example.com/fellowship",
                "source": "nih.gov",
                "displayed_link": "nih.gov/fellowships",
            },
        ]
    }


# ============== Environment Fixtures ==============


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up required environment variables for testing."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key-12345")
    monkeypatch.setenv("SERP_API", "test-serp-api-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000")


@pytest.fixture
def temp_config_file(tmp_path, sample_search_config):
    """Create a temporary search_parameters.json file."""
    import json

    config_file = tmp_path / "search_parameters.json"
    config_file.write_text(json.dumps(sample_search_config))
    return config_file


# ============== FastAPI Test Fixtures ==============


@pytest.fixture
def mock_app_state():
    """Mock FastAPI app state with Supabase client."""
    state = MagicMock()
    state.supabase = MagicMock()
    return state
