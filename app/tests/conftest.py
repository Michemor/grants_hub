# app/tests/conftest.py
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_grant_data():
    return [
        {
            "title": "Clean Energy Grant 2026",
            "snippet": "Funding for solar projects. Deadline: 25 Oct 2026",
            "link": "https://example.com/solar",
            "school": "Science, Engineering and Health"
        }
    ]

@pytest.fixture
def mock_supabase():
    # This creates a fake Supabase client that won't write to your real database
    mock_client = MagicMock()
    mock_client.table().upsert().execute.return_value = MagicMock(data=[{"id": 1}])
    return mock_client