# app/tests/test_filter_service.py
"""
Unit tests for the FilterService class.
"""
from datetime import datetime, timedelta

from services.filter_service import (
    FilterService,
    DEFAULT_MAX_DEADLINE_DAYS,
    DEFAULT_RELEVANCE_THRESHOLD,
)


class TestFilterServiceInit:
    """Tests for FilterService initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        service = FilterService()

        assert service.search_config == {}
        assert service.max_deadline_days == DEFAULT_MAX_DEADLINE_DAYS
        assert service.relevance_threshold == DEFAULT_RELEVANCE_THRESHOLD
        assert service.enable_debug_output is False
        assert service._genai_client is None

    def test_init_with_custom_config(self, sample_search_config):
        """Test initialization with custom configuration."""
        service = FilterService(
            search_config=sample_search_config,
            max_deadline_days=180,
            relevance_threshold=4,
            enable_debug_output=True,
        )

        assert service.search_config == sample_search_config
        assert service.max_deadline_days == 180
        assert service.relevance_threshold == 4
        assert service.enable_debug_output is True


class TestNormalizeGrants:
    """Tests for the _normalize_grants method."""

    def test_normalize_single_grant(self, sample_raw_grant):
        """Test normalizing a single grant."""
        service = FilterService()
        normalized = service._normalize_grants([sample_raw_grant])

        assert len(normalized) == 1
        assert normalized[0]["title"] == "Clean Energy Research Grant 2026"
        assert normalized[0]["school"] == "School of Science"
        assert "funding_link" in normalized[0]

    def test_normalize_strips_whitespace(self):
        """Test that normalization strips whitespace from fields."""
        service = FilterService()
        grant_with_whitespace = {
            "title": "  Test Grant  ",
            "snippet": "\n Description here \t",
            "funding_link": " https://example.com ",
            "organization": "Org",
            "source": "src",
            "deadline": "2027-01-01",
            "date_scraped": "2026-01-01",
            "school": " School ",
        }

        normalized = service._normalize_grants([grant_with_whitespace])

        assert normalized[0]["title"] == "Test Grant"
        assert normalized[0]["snippet"] == "Description here"
        assert normalized[0]["funding_link"] == "https://example.com"
        assert normalized[0]["school"] == "School"

    def test_normalize_handles_missing_fields(self):
        """Test normalization with missing fields."""
        service = FilterService()
        incomplete_grant = {"title": "Partial Grant"}

        normalized = service._normalize_grants([incomplete_grant])

        assert normalized[0]["title"] == "Partial Grant"
        assert normalized[0]["snippet"] == ""
        assert normalized[0]["funding_link"] == ""


class TestDeduplicateGrants:
    """Tests for the _deduplicate_grants method."""

    def test_removes_duplicates(self, sample_raw_grants):
        """Test that duplicates are removed."""
        service = FilterService()
        normalized = service._normalize_grants(sample_raw_grants)
        unique = service._deduplicate_grants(normalized)

        # Original has 3, but 2 share the same funding_link
        assert len(unique) == 2

    def test_keeps_unique_grants(self):
        """Test that unique grants are preserved."""
        service = FilterService()
        grants = [
            {"title": "Grant A", "funding_link": "https://a.com"},
            {"title": "Grant B", "funding_link": "https://b.com"},
            {"title": "Grant C", "funding_link": "https://c.com"},
        ]

        unique = service._deduplicate_grants(grants)

        assert len(unique) == 3


class TestFilterByRelevance:
    """Tests for the _filter_by_relevance method."""

    def test_filters_by_priority_keywords(self, sample_search_config):
        """Test filtering based on priority keywords."""
        service = FilterService(
            search_config=sample_search_config,
            relevance_threshold=2,
        )

        grants = [
            {
                "title": "AI Grant Funding",  # Contains "AI", "grant", "funding"
                "snippet": "Research opportunity",  # Contains "research"
                "school": "School of Technology",
            },
        ]

        filtered = service._filter_by_relevance(grants)

        assert len(filtered) == 1
        # 4 keywords * 2 weight = 8
        assert filtered[0]["relevance_score"] >= 6

    def test_excludes_low_relevance(self, sample_search_config):
        """Test that low relevance grants are excluded."""
        service = FilterService(
            search_config=sample_search_config,
            relevance_threshold=4,
        )

        grants = [
            {
                "title": "Unrelated Topic",
                "snippet": "Nothing relevant here",
                "school": "School of Technology",
            },
        ]

        filtered = service._filter_by_relevance(grants)

        assert len(filtered) == 0

    def test_exclude_keywords_reduce_score(self, sample_search_config):
        """Test that exclude keywords reduce the relevance score."""
        service = FilterService(
            search_config=sample_search_config,
            relevance_threshold=10,  # High threshold
        )

        grants = [
            {
                "title": "Grant News Blog",  # Has "news" and "blog" (excluded)
                "snippet": "AI funding research",  # Has priority keywords
                "school": "School of Technology",
            },
        ]

        filtered = service._filter_by_relevance(grants)

        # Score: 3*2 (priority) - 2*2 (exclude) = 2
        # Below threshold of 10
        assert len(filtered) == 0


class TestFilterByDeadline:
    """Tests for the _filter_by_deadline method."""

    def test_accepts_future_deadline(self):
        """Test that grants with future deadlines are accepted."""
        service = FilterService(max_deadline_days=365)

        future_date = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")
        grants = [
            {
                "title": f"Grant with deadline {future_date}",
                "snippet": f"Apply by {future_date}",
                "relevance_score": 5,
            },
        ]

        filtered = service._filter_by_deadline(grants)

        assert len(filtered) == 1

    def test_rejects_past_deadline(self):
        """Test that grants with past deadlines are rejected."""
        service = FilterService(max_deadline_days=365)

        grants = [
            {
                "title": "Old Grant",
                "snippet": "Deadline was January 1, 2020",
            },
        ]

        filtered = service._filter_by_deadline(grants)

        assert len(filtered) == 0

    def test_rejects_far_future_deadline(self):
        """Test that grants with deadlines too far in the future are rejected."""
        service = FilterService(max_deadline_days=30)

        far_future = (datetime.now() + timedelta(days=100)).strftime("%B %d, %Y")
        grants = [
            {
                "title": "Grant with far deadline",
                "snippet": f"Deadline: {far_future}",
            },
        ]

        filtered = service._filter_by_deadline(grants)

        assert len(filtered) == 0


class TestExtractDeadline:
    """Tests for the _extract_deadline method."""

    def test_extracts_date_format_1(self):
        """Test extraction of 'Month DD, YYYY' format."""
        service = FilterService()

        deadline = service._extract_deadline("Deadline: March 15, 2027")

        assert deadline is not None
        assert deadline.year == 2027
        assert deadline.month == 3
        assert deadline.day == 15

    def test_extracts_date_format_2(self):
        """Test extraction of 'DD Mon YYYY' format."""
        service = FilterService()

        deadline = service._extract_deadline("Applications due 25 Oct 2026")

        assert deadline is not None
        assert deadline.year == 2026
        assert deadline.month == 10
        assert deadline.day == 25

    def test_extracts_date_format_3(self):
        """Test extraction of 'MM/DD/YYYY' format."""
        service = FilterService()

        deadline = service._extract_deadline("Due date: 01/15/2027")

        assert deadline is not None
        assert deadline.year == 2027

    def test_returns_none_for_no_date(self):
        """Test that None is returned when no date is found."""
        service = FilterService()

        deadline = service._extract_deadline("No deadline mentioned here")

        assert deadline is None


class TestGenerateGrantHash:
    """Tests for the _generate_grant_hash method."""

    def test_generates_consistent_hash(self):
        """Test that the same grant produces the same hash."""
        service = FilterService()

        grant = {"title": "Test Grant", "funding_link": "https://example.com"}

        hash1 = service._generate_grant_hash(grant)
        hash2 = service._generate_grant_hash(grant)

        assert hash1 == hash2

    def test_different_grants_different_hashes(self):
        """Test that different grants produce different hashes."""
        service = FilterService()

        grant1 = {"title": "Grant A", "funding_link": "https://a.com"}
        grant2 = {"title": "Grant B", "funding_link": "https://b.com"}

        hash1 = service._generate_grant_hash(grant1)
        hash2 = service._generate_grant_hash(grant2)

        assert hash1 != hash2

    def test_case_insensitive_hash(self):
        """Test that hashing is case-insensitive."""
        service = FilterService()

        grant1 = {"title": "TEST GRANT", "funding_link": "HTTPS://EXAMPLE.COM"}
        grant2 = {"title": "test grant", "funding_link": "https://example.com"}

        hash1 = service._generate_grant_hash(grant1)
        hash2 = service._generate_grant_hash(grant2)

        assert hash1 == hash2


class TestProcessGrants:
    """Integration tests for the full process_grants pipeline."""

    def test_full_pipeline(self, sample_raw_grants, sample_search_config):
        """Test the complete processing pipeline."""
        service = FilterService(
            search_config=sample_search_config,
            relevance_threshold=2,
            max_deadline_days=400,  # Allow future dates
        )

        # Modify grants to have valid future deadlines
        for grant in sample_raw_grants:
            future_date = (datetime.now() + timedelta(days=60)).strftime("%B %d, %Y")
            grant["snippet"] = f"Grant funding research. Deadline: {future_date}"

        processed = service.process_grants(sample_raw_grants)

        # Should have fewer grants after filtering
        assert len(processed) <= len(sample_raw_grants)

        # Each processed grant should have relevance_score
        for grant in processed:
            assert "relevance_score" in grant
            assert grant["relevance_score"] >= service.relevance_threshold
