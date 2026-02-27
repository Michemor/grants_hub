from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any


# ============== Input Models ==============


class GrantItem(BaseModel):
    """Grant item for email digest requests."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=2000)
    deadline: str = Field(default="Check link for deadline")
    funding_organization: str = Field(default="Unknown")
    funding_link: str
    school_name: str = Field(default="Unknown")
    school_abbreviation: Optional[str] = None
    ai_confidence_score: Optional[float] = None


class DigestEmail(BaseModel):
    """Request model for generating email digests."""

    school_email: EmailStr
    school_name: str = Field(..., min_length=1, max_length=200)
    grants: List[GrantItem] = Field(..., min_length=1)


# ============== Database/Internal Models ==============


class ScrapedGrant(BaseModel):
    """Model for grants returned from the scraper service."""

    title: str
    snippet: str
    funding_link: str
    organization: str
    source: str
    deadline: str
    date_scraped: str
    school: str

    class Config:
        extra = "ignore"


class ProcessedGrant(BaseModel):
    """Model for grants after processing/filtering."""

    title: str
    snippet: str
    funding_link: str
    organization: str
    source: str
    deadline: str
    date_scraped: str
    school: str
    relevance_score: int = 0
    ai_metadata: Optional[dict] = None
    ai_confidence_score: float = 0.0

    class Config:
        extra = "ignore"


# ============== Response Models ==============


class GrantResponse(BaseModel):
    """Single grant response from database."""

    title: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    funder: Optional[str] = None
    deadline: Optional[str] = None
    school: Optional[str] = None
    school_abbreviation: Optional[str] = None
    ai_confidence_score: Optional[float] = None
    created_at: Optional[str] = None

    class Config:
        extra = "allow"


class SchoolResponse(BaseModel):
    """Single school response from database."""
    school_name: Optional[str] = None
    school_description: Optional[Any] = None
    school_abbreviation: Optional[str] = None

    class Config:
        extra = "allow"


class GrantListResponse(BaseModel):
    """Response model for multiple grants."""

    grants: List[GrantResponse] = []


class SchoolListResponse(BaseModel):
    """Response model for multiple schools."""

    schools: List[SchoolResponse] = []


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str
