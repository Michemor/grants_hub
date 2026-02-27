import os
import logging
from fastapi import FastAPI, HTTPException, Query
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from email.message import EmailMessage
from contextlib import asynccontextmanager
from .run_pipeline import run_pipeline
from supabase import create_client, Client
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .models.models import DigestEmail, GrantListResponse, SchoolListResponse

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def populate_initial_data(supabase: Client):
    """Check if grants exist in the database and populate if empty."""
    logger.info("Checking for existing grants...")
    try:
        response = (
            supabase.table("grants")
            .select("grant_id", count="exact")
            .limit(1)
            .execute()
        )
        if not response.data:
            logger.info("No grants found. Running initial data population...")
            run_pipeline()
        else:
            logger.info("Grants already exist. Skipping initial population.")
    except Exception as e:
        logger.error(f"Error checking initial data: {e}", exc_info=True)


def weekly_update():
    """Scheduled task to refresh grant data weekly."""
    logger.info("Starting weekly update...")
    try:
        run_pipeline()
        logger.info("Weekly update completed successfully.")
    except Exception as e:
        logger.error(f"Error during weekly update: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    logger.info("Starting up the application...")

    # Validate required environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "Missing required environment variables: SUPABASE_URL and SUPABASE_KEY must be set."
        )

    app.state.supabase = create_client(supabase_url, supabase_key)
    logger.info("Supabase client initialized successfully.")

    # Check and populate initial data
    populate_initial_data(supabase=app.state.supabase)

    # Schedule weekly updates
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        weekly_update,
        CronTrigger(day_of_week="sun", hour=0, minute=0),
        id="weekly_grant_update",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler for weekly updates started.")

    yield

    # Cleanup
    logger.info("Shutting down the application...")
    scheduler.shutdown(wait=False)
    app.state.supabase = None
    logger.info("Resources cleaned up successfully.")


app = FastAPI(
    lifespan=lifespan,
    title="Daystar Grant Hub",
    description="API for managing and retrieving grant information for schools",
    version="1.0.0",
)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://grants-intelligence-hub.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)


def _normalize_grant_schools(rows):
    """Attach associated schools and derived school fields to each grant row.

    Expects Supabase rows selected with:
        schools_grants( schools(school_id, school_name, school_abbreviation) )

    Returns a new list where each grant has:
        - schools: list of school dicts
        - school: primary school_name (for backward compatibility)
        - school_abbreviation: primary school_abbreviation
    """
    if not rows:
        return []

    normalized = []

    for grant in rows:
        # Safely gather schools from the join table
        schools = []
        for link in grant.get("schools_grants") or []:
            school = link.get("schools") if isinstance(link, dict) else None
            if school:
                schools.append(school)

        grant["schools"] = schools

        if schools:
            primary = schools[0]
            grant["school"] = primary.get("school_name")
            grant["school_abbreviation"] = primary.get("school_abbreviation")
        else:
            grant["school"] = None
            grant["school_abbreviation"] = None

        # Remove the raw join key to keep the payload clean
        grant.pop("schools_grants", None)
        normalized.append(grant)

    return normalized


@app.get("/api")
async def root():
    """
    Health check endpoint.
    """

    instructions = """Welcome to the Daystar Grant Hub API!
    Available endpoints:
    - GET /api/grants: Retrieve all grants
    - GET /api/grants/search?query=...: Search grants by title
    - GET /api/grants/{school_name}: Get grants for a specific school
    - GET /api/schools: Retrieve all schools
    - POST /api/email: Generate an email digest for grant opportunities
    - GET /api/fetch-grants: Trigger grant fetching and processing
    """
    return {
        "message": "Daystar Grant Hub API is running!",
        "instructions": instructions,
    }


@app.get("/api/grants", response_model=GrantListResponse)
async def get_all_grants():
    """Retrieve all grants from the database."""
    try:
        response = (
            app.state.supabase.table("grants")
            .select(
                "title, description, link, funder, deadline, ai_confidence_score, "
                "schools_grants("
                "  schools(school_name, school_abbreviation)"
                ")"
            )
            .execute()
        )

        count_response = (
            app.state.supabase.table("grants")
            .select(
                "title, description, link, funder, deadline, ai_confidence_score",
                count="exact",
            )
            .execute()
        )
        total_grants = (
            count_response.count if count_response.count is not None else "unknown"
        )
        grants = _normalize_grant_schools(response.data)
        logger.info(f"Fetched {len(grants)} grants from the database (with schools).")
        return {"grants": grants, "total_grants": total_grants}
    except Exception as e:
        logger.error(f"Error fetching grants: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to fetch grants from the database."
        )


@app.get("/api/grants/search", response_model=GrantListResponse)
async def search_grants(query: str = Query(..., min_length=1, max_length=200)):
    """Search grants by title."""
    try:
        # Sanitize: escape special characters for LIKE pattern
        sanitized_query = query.replace("%", "\\%").replace("_", "\\_")
        response = (
            app.state.supabase.table("grants")
            .select(
                "title, description, link, funder, deadline, ai_confidence_score, "
                "schools_grants("
                "  schools(school_name, school_abbreviation)"
                ")"
            )
            .ilike("title", f"%{sanitized_query}%")
            .execute()
        )
        count_response = (
            app.state.supabase.table("grants")
            .select("*", count="exact")
            .ilike("title", f"%{sanitized_query}%")
            .execute()
        )
        total_grants = (
            count_response.count if count_response.count is not None else "unknown"
        )
        grants = _normalize_grant_schools(response.data)
        logger.info(f"Search for '{query}' returned {len(grants)} grants.")
        return {"grants": grants, "total_grants": total_grants}
    except Exception as e:
        logger.error(f"Error searching grants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search grants.")


@app.get("/api/grants/{school_name}", response_model=GrantListResponse)
async def get_grants_by_school(school_name: str):
    """
    Retrieve grants for a specific school.

    Uses the schools_grants join table to resolve the many-to-many
    association between grants and schools.
    """
    try:
        # 1) Verify school exists and get its id and abbreviation
        school_response = (
            app.state.supabase.table("schools")
            .select("school_name, school_abbreviation")
            .eq("school_name", school_name)
            .limit(1)
            .execute()
        )

        if not school_response.data:
            raise HTTPException(
                status_code=404, detail=f"School '{school_name}' not found."
            )

        school = school_response.data[0]
        school_id = school.get("school_id")

        # 2) Fetch all grants linked to this school via the join table
        link_response = (
            app.state.supabase.table("schools_grants")
            .select(
                "grants(title, description, link, funder, deadline, ai_confidence_score), "
                "schools(school_name, school_abbreviation)"
            )
            .eq("school_id", school_id)
            .execute()
        )

        grants = []
        for row in link_response.data or []:
            grant = row.get("grants") or {}
            s = row.get("schools")

            if s:
                grant["schools"] = [s]
                grant["school"] = s.get("school_name")
                grant["school_abbreviation"] = s.get("school_abbreviation")
            else:
                grant["schools"] = []
                grant["school"] = None
                grant["school_abbreviation"] = None

            grants.append(grant)

        logger.info(
            f"Fetched {len(grants)} grants for school '{school_name}' (id={school_id})."
        )
        return {"grants": grants}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching grants for school '{school_name}': {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch grants for school '{school_name}'.",
        )


@app.get("/api/schools", response_model=SchoolListResponse)
async def get_all_schools():
    """Retrieve all schools from the database."""
    try:
        response = (
            app.state.supabase.table("schools")
            .select("school_name, school_abbreviation")
            .execute()
        )
        logger.info(
            f"Fetched {len(response.data) if response.data else 0} schools from the database."
        )
        return {"schools": response.data or []}
    except Exception as e:
        logger.error(f"Error fetching schools: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to fetch schools from the database."
        )


@app.get("/api/grants/{grant_name}/schools", response_model=SchoolListResponse)
async def get_schools_by_grant(grant_name: str):
    """Retrieve all schools associated with a specific grant via schools_grants."""
    try:
        # Ensure the grant exists
        grant_check = (
            app.state.supabase.table("grants")
            .select("grant_id")
            .eq("grant_name", grant_name)
            .limit(1)
            .execute()
        )

        if not grant_check.data:
            raise HTTPException(
                status_code=404, detail=f"Grant with name '{grant_name}' not found."
            )

        grant_id = grant_check.data[0]["grant_id"]

        # Fetch schools linked to this grant via the join table
        link_response = (
            app.state.supabase.table("schools_grants")
            .select(
                "schools(school_name, school_description, school_abbreviation)"
            )
            .eq("grant_id", grant_id)
            .execute()
        )

        schools = [
            row["schools"] for row in (link_response.data or []) if row.get("schools")
        ]

        logger.info(
            f"Fetched {len(schools)} schools for grant_name='{grant_name}' (grant_id={grant_id})."
        )
        return {"schools": schools}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching schools for grant_name='{grant_name}': {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch schools for the specified grant.",
        )


@app.post("/api/email")
async def send_email(request: DigestEmail):
    """Generate an email digest file for grant opportunities."""
    try:
        email_message = EmailMessage()
        email_message["Subject"] = f"New Grant Opportunities for {request.school_name}"
        email_message["To"] = request.school_email
        email_message["X-Unsent"] = "1"

        # Build email content using list comprehension for efficiency
        grant_entries = [
            f"{i}. {grant.title}\n"
            f"   Description: {grant.description}\n"
            f"   Deadline: {grant.deadline}\n"
            f"   Funding Organization: {grant.funding_organization}\n"
            f"   More Info: {grant.funding_link}\n"
            for i, grant in enumerate(request.grants, start=1)
        ]

        email_body = (
            f"Hello {request.school_name} Team,\n\n"
            f"Here are the latest grant opportunities:\n\n"
            f"{''.join(grant_entries)}\n"
            f"Best regards,\nDaystar Grant Hub Team"
        )
        email_message.set_content(email_body)

        # Sanitize filename to prevent path traversal
        safe_name = "".join(
            c for c in request.school_name if c.isalnum() or c in " _-"
        ).strip()
        filename = f"{safe_name}_grant_digest.eml"

        logger.info(
            f"Generated email digest for {request.school_name} with {len(request.grants)} grants."
        )
        return Response(
            content=email_message.as_string(),
            media_type="message/rfc822",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Error generating email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate email.")


@app.get("/api/fetch-grants")
async def fetch_grants():
    """Endpoint to trigger grant fetching and processing."""
    try:
        run_pipeline()
        logger.info("Grant fetching and processing completed successfully.")
        return {"message": "Grant fetching and processing completed successfully."}
    except Exception as e:
        logger.error(f"Error in fetch-grants endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to fetch and process grants."
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
