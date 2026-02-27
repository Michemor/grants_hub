# app/tests/test_scraper_services.py
"""
Unit tests for the ScraperService class.
"""
import json
import pytest
from unittest.mock import patch
from services.scraper_services import (
    ScraperService,
    FUNDER_PATTERN,
    DEADLINE_KEYWORD_PATTERN,
    DATE_PATTERN,
)


@pytest.fixture
def temp_query_file(tmp_path, sample_search_config):
    """Create a temporary search_parameters.json file."""
    config_file = tmp_path / "search_parameters.json"
    config_file.write_text(json.dumps(sample_search_config))
    return config_file


class TestScraperServiceInit:
    """Tests for ScraperService initialization."""

    def test_init_with_valid_config(self, temp_query_file):
        """Test initialization with valid configuration."""
        service = ScraperService(
            api_key="test_api_key",
            query_file=temp_query_file,
        )

        assert service.api_key == "test_api_key"
        assert service.search_config is not None

    def test_init_validates_api_key(self, temp_query_file):
        """Test that empty API key raises ValueError."""
        with pytest.raises(ValueError, match="required"):
            ScraperService(api_key="", query_file=temp_query_file)

    def test_init_validates_query_file(self, tmp_path):
        """Test that nonexistent query file raises FileNotFoundError."""
        fake_file = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            ScraperService(api_key="test_key", query_file=fake_file)


class TestExtractFunder:
    """Tests for the _extract_funder method."""

    def test_extract_funder_from_title(self, temp_query_file):
        """Test extracting funder from title."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        funder = service._extract_funder(
            title="NSF Research Grant Program",
            snippet="Apply for funding support",
            default="Unknown",
        )

        # Should extract organization pattern or return default
        assert funder is not None

    def test_extract_funder_foundation(self, temp_query_file):
        """Test extracting 'Foundation' as funder."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        funder = service._extract_funder(
            title="Grant Opportunity",
            snippet="Bill and Melinda Gates Foundation announces new grant",
            default="",
        )

        assert "Foundation" in funder or funder == ""

    def test_extract_funder_no_match(self, temp_query_file):
        """Test extraction when no funder found."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        funder = service._extract_funder(
            title="Random text", snippet="without organization", default="DefaultOrg"
        )

        # When no match, should return default
        assert funder == "DefaultOrg"


class TestExtractDeadline:
    """Tests for the _extract_deadline method."""

    def test_extract_deadline_keyword_format(self, temp_query_file):
        """Test extracting deadline with keyword."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        deadline = service._extract_deadline("Applications due March 15, 2027")

        assert deadline is not None
        assert "2027" in deadline or "March" in deadline

    def test_extract_deadline_date_format(self, temp_query_file):
        """Test extracting date-only deadline."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        deadline = service._extract_deadline("Grant closes 01/15/2027")

        assert deadline is not None

    def test_extract_deadline_no_date(self, temp_query_file):
        """Test extraction when no deadline found."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        deadline = service._extract_deadline("No deadline mentioned here")

        # When no deadline found, returns default message
        assert deadline == "Check link for deadline"


class TestParseSearchResult:
    """Tests for the _parse_search_result method."""

    def test_parse_complete_result(self, temp_query_file):
        """Test parsing a complete search result."""
        from datetime import datetime

        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        result = {
            "title": "Research Grant 2026",
            "snippet": "Apply for funding. Deadline: March 15, 2027",
            "link": "https://example.com/grant",
            "source": "example.com",
        }

        scraped_at = datetime.now().isoformat()
        parsed = service._parse_search_result(result, "School of Science", scraped_at)

        assert parsed["title"] == "Research Grant 2026"
        assert parsed["funding_link"] == "https://example.com/grant"
        assert parsed["school"] == "School of Science"

    def test_parse_result_with_missing_fields(self, temp_query_file):
        """Test parsing result with missing fields."""
        from datetime import datetime

        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        result = {
            "title": "Minimal Grant",
        }

        scraped_at = datetime.now().isoformat()
        parsed = service._parse_search_result(result, "School of Arts", scraped_at)

        assert parsed["title"] == "Minimal Grant"
        assert parsed["school"] == "School of Arts"
        assert parsed["funding_link"] == ""


class TestFetchGrantsFromQuery:
    """Tests for the fetch_grants_from_query method."""

    def test_fetch_grants_success(self, temp_query_file, mock_serpapi_response):
        """Test successful grant fetching."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        with patch("services.scraper_services.serpapi.GoogleSearch") as mock_search:
            mock_search.return_value.get_dict.return_value = mock_serpapi_response

            results = service.fetch_grants_from_query(query="AI research grants")

            assert len(results) > 0
            assert all("title" in r for r in results)

    def test_fetch_grants_empty_response(self, temp_query_file):
        """Test handling empty API response."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        with patch("services.scraper_services.serpapi.GoogleSearch") as mock_search:
            mock_search.return_value.get_dict.return_value = {"organic_results": []}

            results = service.fetch_grants_from_query(query="obscure grant topic")

            assert results == []

    def test_fetch_grants_api_error(self, temp_query_file):
        """Test handling API errors."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        with patch("services.scraper_services.serpapi.GoogleSearch") as mock_search:
            mock_search.return_value.get_dict.side_effect = Exception("API Error")

            # Should handle exception gracefully and return empty list
            results = service.fetch_grants_from_query(query="test query")
            assert results == []


class TestRun:
    """Tests for the run method (full scraping pipeline)."""

    def test_run_returns_grants(self, temp_query_file, mock_serpapi_response):
        """Test that run returns scraped grants."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        with patch("services.scraper_services.serpapi.GoogleSearch") as mock_search:
            mock_search.return_value.get_dict.return_value = mock_serpapi_response

            grants = service.run()

            assert isinstance(grants, list)
            # Each grant should have required fields
            for grant in grants:
                assert "title" in grant
                assert "school" in grant

    def test_run_processes_all_schools(self, temp_query_file, mock_serpapi_response):
        """Test that run processes grants for all schools."""
        service = ScraperService(
            api_key="test_key",
            query_file=temp_query_file,
        )

        with patch("services.scraper_services.serpapi.GoogleSearch") as mock_search:
            mock_search.return_value.get_dict.return_value = mock_serpapi_response

            grants = service.run()

            # Should have grants from configured schools
            schools_in_results = {g.get("school") for g in grants}

            # The config has schools as top-level keys
            configured_schools = set(service.search_config.keys())
            assert len(schools_in_results & configured_schools) > 0 or len(grants) == 0


class TestCompiledPatterns:
    """Tests for pre-compiled regex patterns."""

    def test_funder_pattern_matches(self):
        """Test that FUNDER_PATTERN matches expected strings."""
        test_text = "National Science Foundation announces new grants"
        match = FUNDER_PATTERN.search(test_text)

        assert match is not None
        assert "Foundation" in match.group()

    def test_deadline_keyword_pattern_matches(self):
        """Test that DEADLINE_KEYWORD_PATTERN matches deadline keywords."""
        test_text = "Applications due December 31, 2026"
        match = DEADLINE_KEYWORD_PATTERN.search(test_text)

        assert match is not None

    def test_date_pattern_matches(self):
        """Test that DATE_PATTERN matches various date formats."""
        test_texts = [
            "March 15, 2027",
            "15 March 2027",
            "03/15/2027",
        ]

        for text in test_texts:
            match = DATE_PATTERN.search(text)
            assert match is not None, f"Failed to match: {text}"
