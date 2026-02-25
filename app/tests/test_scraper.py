import os
from fastapi import FastAPI
import supabase
import uvicorn
from contextlib import asynccontextmanager
from run_pipeline import run_pipeline
from supabase import create_client
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

def populate_initial_data():
    print("Populating initial data...")
    try:
        response = supabase.table("grants").select("grant_id", count="exact").limit(1).execute()
        if response.data and len(response.data) == 0:
            print("No grants found in the database. Running initial data population..." )
            run_pipeline()
        else:
            print("Grants already exist in the database. Skipping initial data population.")
    except Exception as e:
        print(f"Error checking initial data: {e}")

def weekly_update():
    print("Starting weekly update...")
    try:
        run_pipeline()
        print("Weekly update completed successfully.")
    except Exception as e:
        print(f"Error during weekly update: {e}")   

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize resources here (e.g., database connections, clients)
    print("Starting up the application...")

    # Initialize supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("Supabase URL or Key not found in environment variables. Please set SUPABASE_URL and SUPABASE_KEY.")
        return
    
    app.state.supabase = create_client(supabase_url, supabase_key)
    print("Supabase client initialized successfully.")

    # Check and populate initial data
    populate_initial_data()

    # Schedule weekly updates (this is a placeholder - in production, use a proper scheduler like Celery or APScheduler)
    scheduler = BackgroundScheduler()
    scheduler.add_job(weekly_update, CronTrigger(day_of_week='sun', hour=0, minute=0))  # Every Sunday at midnight
    scheduler.start()
    print("Scheduler for weekly updates started.")

    yield  # This is where the application runs
    
    # Clean up resources here
    print("Shutting down the application...")
    scheduler.shutdown()
    app.state.supabase = None
    print("Resources cleaned up successfully.")

app = FastAPI(lifespan=lifespan)

@app.get("/api")
async def root():
    return {"message": "Daystar Grant hub is live"}

@app.get("/api/grants")
async def get_all_grants():
    try:
        response = app.state.supabase.table("grants").select("*").execute()
        if response.data:
            return {"grants": response.data}
        else:
            return {"message": "No grants found in the database."}
    except Exception as e:
        print(f"Error fetching grants: {e}")
        return {"error": "Failed to fetch grants from the database."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
