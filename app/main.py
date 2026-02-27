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

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(
        ","
    ),  # Adjust to fit frontend domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.get("/api")
async def root():
    """Health check endpoint."""
    return {"message": "Daystar Grant hub is live"}


@app.get("/api/grants", response_model=GrantListResponse)
async def get_all_grants():
    """Retrieve all grants from the database."""
    try:
        response = app.state.supabase.table("grants").select("*").execute()
        return {"grants": response.data or []}
    except Exception as e:
        logger.error(f"Error fetching grants: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to fetch grants from the database."
        )


            # IMPORTANT: /search must come BEFORE /{school_name} to avoid route conflicts
@app.get("/api/grants/search", response_model=GrantListResponse)
async def search_grants(query: str = Query(..., min_length=1, max_length=200)):
    """Search grants by title."""
    try:
        # Sanitize: escape special characters for LIKE pattern
        sanitized_query = query.replace("%", "\\%").replace("_", "\\_")
        response = (
            app.state.supabase.table("grants")
            .select("*")
            .ilike("title", f"%{sanitized_query}%")
            .execute()
        )
        return {"grants": response.data or []}
    except Exception as e:
        logger.error(f"Error searching grants: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search grants.")


@app.get("/api/grants/{school_name}", response_model=GrantListResponse)
async def get_grants_by_school(school_name: str):
    """
    Retrieve grants for a specific school.

    Queries the grants table directly using the school column.
    """
    try:
        # Verify school exists
        school_response = (
            app.state.supabase.table("schools")
            .select("school_id")
            .eq("school_name", school_name)
            .execute()
        )

        if not school_response.data:
            raise HTTPException(
                status_code=404, detail=f"School '{school_name}' not found."
            )

        # Query grants directly by school column
        grants_response = (
            app.state.supabase.table("grants")
            .select("*")
            .eq("school", school_name)
            .execute()
        )

        return {"grants": grants_response.data or []}
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
        response = app.state.supabase.table("schools").select("*").execute()
        return {"schools": response.data or []}
    except Exception as e:
        logger.error(f"Error fetching schools: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to fetch schools from the database."
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

        return Response(
            content=email_message.as_string(),
            media_type="message/rfc822",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.error(f"Error generating email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate email.")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
