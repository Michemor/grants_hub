# app/tests/test_filter.py
from app.services.filter_service import FilterService

def test_pipeline_normalization(mock_grant_data):
    # We supply empty configs and a fake API key just to test the basic logic
    filter_service = FilterService(search_config={})
    
    # Run the normalize step directly
    normalized = filter_service._normalize(mock_grant_data)
    
    assert len(normalized) == 1
    assert normalized[0]["title"] == "Clean Energy Grant 2026"
    assert "funding_link" in normalized[0] # Checks if the key was standardized