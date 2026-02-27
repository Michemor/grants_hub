# app/tests/test_models.py
"""
Unit tests for Pydantic models.
"""
import pytest
from pydantic import ValidationError

from models.models import (
    GrantItem,
    DigestEmail,
    GrantResponse,
    SchoolResponse,
    GrantListResponse,
    SchoolListResponse,
    ScrapedGrant,
    ProcessedGrant,
)


class TestGrantItem:
    """Tests for the GrantItem model."""

    def test_valid_grant_item(self):
        """Test creating a valid GrantItem."""
        grant = GrantItem(
            title="Research Grant 2026",
            description="Funding for research projects",
            funding_link="https://example.com/grant",
            funding_organization="National Science Foundation",
            deadline="2026-12-31",
        )

        assert grant.title == "Research Grant 2026"
        assert grant.funding_link == "https://example.com/grant"
        assert grant.funding_organization == "National Science Foundation"

    def test_grant_item_with_defaults(self):
        """Test GrantItem with only required fields (title, funding_link)."""
        grant = GrantItem(
            title="Basic Grant",
            funding_link="https://example.com/grant",
        )

        assert grant.title == "Basic Grant"
        assert grant.description == ""
        assert grant.deadline == "Check link for deadline"
        assert grant.funding_organization == "Unknown"

    def test_grant_item_empty_title_validation(self):
        """Test that empty title raises validation error."""
        with pytest.raises(ValidationError):
            GrantItem(title="", funding_link="https://example.com")

    def test_grant_item_missing_funding_link(self):
        """Test that missing funding_link raises validation error."""
        with pytest.raises(ValidationError):
            GrantItem(title="Test Grant")


class TestDigestEmail:
    """Tests for the DigestEmail model."""

    def test_valid_digest_email(self):
        """Test creating a valid DigestEmail."""
        grants = [
            GrantItem(title="Grant 1", funding_link="https://example.com/1"),
            GrantItem(title="Grant 2", funding_link="https://example.com/2"),
        ]
        digest = DigestEmail(
            school_email="user@example.com",
            school_name="School of Technology",
            grants=grants,
        )

        assert digest.school_email == "user@example.com"
        assert digest.school_name == "School of Technology"
        assert len(digest.grants) == 2

    def test_invalid_email_format(self):
        """Test that invalid email raises validation error."""
        grants = [GrantItem(title="Grant", funding_link="https://example.com")]
        with pytest.raises(ValidationError):
            DigestEmail(
                school_email="not-an-email",
                school_name="School of Technology",
                grants=grants,
            )

    def test_missing_required_fields(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError):
            DigestEmail(school_name="School of Technology")

    def test_empty_grants_list(self):
        """Test that empty grants list raises validation error."""
        with pytest.raises(ValidationError):
            DigestEmail(
                school_email="user@example.com",
                school_name="School of Technology",
                grants=[],
            )


class TestScrapedGrant:
    """Tests for the ScrapedGrant model."""

    def test_valid_scraped_grant(self):
        """Test creating a valid ScrapedGrant."""
        grant = ScrapedGrant(
            title="Scraped Grant",
            snippet="Description from search result",
            funding_link="https://example.com",
            organization="Example Org",
            source="SerpAPI",
            deadline="2026-06-30",
            date_scraped="2026-01-15",
            school="School of Arts",
        )

        assert grant.title == "Scraped Grant"
        assert grant.snippet == "Description from search result"
        assert grant.funding_link == "https://example.com"

    def test_scraped_grant_requires_all_fields(self):
        """Test ScrapedGrant requires all fields."""
        with pytest.raises(ValidationError):
            ScrapedGrant(title="Minimal Grant")

    def test_scraped_grant_extra_fields_ignored(self):
        """Test that extra fields are ignored."""
        grant = ScrapedGrant(
            title="Grant",
            snippet="Desc",
            funding_link="https://example.com",
            organization="Org",
            source="Source",
            deadline="2026-12-31",
            date_scraped="2026-01-01",
            school="School",
            extra_field="ignored",
        )
        assert not hasattr(grant, "extra_field")


class TestProcessedGrant:
    """Tests for the ProcessedGrant model."""

    def test_valid_processed_grant(self):
        """Test creating a valid ProcessedGrant."""
        grant = ProcessedGrant(
            title="Processed Grant",
            snippet="Processed description",
            funding_link="https://example.com/processed",
            organization="Grant Foundation",
            source="test_source",
            deadline="2026-12-31",
            date_scraped="2026-01-01",
            school="School of Science",
            relevance_score=8,
            ai_confidence_score=0.95,
        )

        assert grant.title == "Processed Grant"
        assert grant.relevance_score == 8
        assert grant.ai_confidence_score == 0.95

    def test_processed_grant_defaults(self):
        """Test ProcessedGrant with default values for optional fields."""
        grant = ProcessedGrant(
            title="Grant",
            snippet="Desc",
            funding_link="https://example.com",
            organization="Org",
            source="Source",
            deadline="2026-12-31",
            date_scraped="2026-01-01",
            school="School",
        )

        assert grant.relevance_score == 0
        assert grant.ai_confidence_score == 0.0
        assert grant.ai_metadata is None


class TestGrantResponse:
    """Tests for the GrantResponse model."""

    def test_valid_grant_response(self):
        """Test creating a valid GrantResponse."""
        response = GrantResponse(
            grant_id=1,
            title="Response Grant",
            description="Response description",
            link="https://example.com",
            funder="Example Foundation",
            deadline="2026-12-31",
            school="School of Science",
        )

        assert response.grant_id == 1
        assert response.title == "Response Grant"

    def test_grant_response_optional_fields(self):
        """Test GrantResponse optional fields."""
        response = GrantResponse(
            title="Minimal Response",
        )

        assert response.title == "Minimal Response"
        assert response.grant_id is None

    def test_grant_response_allows_extra_fields(self):
        """Test that GrantResponse allows extra fields."""
        response = GrantResponse(
            title="Grant",
            extra_db_field="value",
        )
        assert response.extra_db_field == "value"


class TestSchoolResponse:
    """Tests for the SchoolResponse model."""

    def test_valid_school_response(self):
        """Test creating a valid SchoolResponse."""
        response = SchoolResponse(
            school_id=1,
            school_name="School of Engineering",
        )

        assert response.school_id == 1
        assert response.school_name == "School of Engineering"

    def test_school_response_allows_extra_fields(self):
        """Test that SchoolResponse allows extra fields."""
        response = SchoolResponse(
            school_name="School",
            custom_field="value",
        )
        assert response.custom_field == "value"


class TestGrantListResponse:
    """Tests for the GrantListResponse model."""

    def test_grants_list_response(self):
        """Test creating a GrantListResponse with multiple grants."""
        grants = [
            GrantResponse(grant_id=1, title="Grant 1"),
            GrantResponse(grant_id=2, title="Grant 2"),
        ]

        response = GrantListResponse(grants=grants)

        assert len(response.grants) == 2
        assert response.grants[0].title == "Grant 1"
        assert response.grants[1].title == "Grant 2"

    def test_empty_grants_list(self):
        """Test creating GrantListResponse with empty list."""
        response = GrantListResponse(grants=[])

        assert len(response.grants) == 0


class TestSchoolListResponse:
    """Tests for the SchoolListResponse model."""

    def test_schools_list_response(self):
        """Test creating a SchoolListResponse with multiple schools."""
        schools = [
            SchoolResponse(school_id=1, school_name="School A"),
            SchoolResponse(school_id=2, school_name="School B"),
        ]

        response = SchoolListResponse(schools=schools)

        assert len(response.schools) == 2
        assert response.schools[0].school_name == "School A"


class TestModelValidation:
    """Tests for model validation edge cases."""

    def test_scraped_grant_extra_fields_ignored(self):
        """Test that extra fields are ignored for ScrapedGrant."""
        grant = ScrapedGrant(
            title="Test Grant",
            snippet="Desc",
            funding_link="https://example.com",
            organization="Org",
            source="Source",
            deadline="2026-12-31",
            date_scraped="2026-01-01",
            school="School",
            extra_field="should be ignored",
        )

        assert grant.title == "Test Grant"
        assert not hasattr(grant, "extra_field")

    def test_type_coercion(self):
        """Test that types are coerced when possible."""
        grant = ProcessedGrant(
            title="Test Grant",
            snippet="Desc",
            funding_link="https://example.com",
            organization="Org",
            source="Source",
            deadline="2026-12-31",
            date_scraped="2026-01-01",
            school="School",
            relevance_score="5",  # String should be coerced to int
        )

        assert grant.relevance_score == 5
        assert isinstance(grant.relevance_score, int)
