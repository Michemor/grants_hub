import os
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from .run_pipeline import run_pipeline
from supabase import create_client, Client
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

load_dotenv()

def populate_initial_data(supabase: Client):
    print("Populating initial data...")
    try:
        response = supabase.table("grants").select("*", count="exact").execute()
        if not response.data or len(response.data) == 0:
            print("No grants found in the database. Running initial data population..." )
            run_pipeline(use_cache=False)  # Use cache to speed up initial population
        else:
            print("Grants already exist in the database. Skipping initial data population.")
    except Exception as e:
        print(f"Error checking initial data: {e}")

def weekly_update():
    print("Starting weekly update...")
    try:
        run_pipeline(use_cache=False)  # Don't use cache for weekly updates to get fresh data
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
    populate_initial_data(supabase=app.state.supabase)

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

@app.get("/api/grants/{school_name}")
async def get_grants_by_school(school_name: str):
    try:
        # First, get the school_id from the school name
        school_response = app.state.supabase.table("schools").select("school_id").eq("school_name", school_name).execute()
        
        if not school_response.data or len(school_response.data) == 0:
            return {"error": f"School '{school_name}' not found in the database."}
        
        school_id = school_response.data[0]["school_id"]
        
        # Now get all grants for this school using the junction table
        # We join grants with schools_grants to filter by school_id
        response = app.state.supabase.table("grants") \
            .select("*") \
            .eq("school_id", school_id)\
            .execute()
        
        if response.data:
            return {"grants": response.data}
        else:
            return {"message": f"No grants found for school '{school_name}'."}
    except Exception as e:
        print(f"Error fetching grants for school '{school_name}': {e}")
        return {"error": f"Failed to fetch grants for school '{school_name}'."} 

@app.get("/api/schools")
async def get_all_schools():
    try:
        response = app.state.supabase.table("schools").select("*").execute()
        if response.data:
            return {"schools": response.data}
        else:
            return {"message": "No schools found in the database."}
    except Exception as e:
        print(f"Error fetching schools: {e}")
        return {"error": "Failed to fetch schools from the database."}  

@app.get("/api/grants/search")
async def search_grants(query: str):
    try:
        response = app.state.supabase.table("grants").select("*").ilike("title", f"%{query}%").execute()
        if response.data:
            return {"grants": response.data}
        else:
            return {"message": "No grants found matching your query."}
    except Exception as e:
        print(f"Error searching grants: {e}")
        return {"error": "Failed to search grants."}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
