# Grants Intelligence Hub

A FastAPI-based application that automatically discovers, filters, and manages grant opportunities for educational institutions. The system scrapes grant data from web sources, processes it using AI-powered filtering, and stores relevant opportunities in a Supabase database.

## Features

- **Automated Grant Discovery** - Scrapes grant opportunities from search engines using SerpAPI
- **AI-Powered Filtering** - Uses Google Gemini to assess grant relevance and filter results
- **School-Specific Grants** - Organizes grants by target schools/institutions
- **Scheduled Updates** - Weekly automated pipeline runs to keep data fresh
- **Email Digest Generation** - Creates downloadable email digests for grant notifications
- **RESTful API** - Full API for querying grants and schools

## Tech Stack

- **Framework**: FastAPI
- **Database**: Supabase (PostgreSQL)
- **AI/ML**: Google Gemini API
- **Web Scraping**: SerpAPI (Google Search Results)
- **Scheduling**: APScheduler
- **Python**: 3.11+

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd grants_intelligence_hub
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\Activate.ps1  # Windows
   # or
   source .venv/bin/activate   # Linux/Mac
   ```

3. Install dependencies:

   ```bash
   uv sync
   ```

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Required
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_api_key

# API Keys
SERP_API=your_serpapi_key
GEMINI_API_KEY=your_google_gemini_api_key

# Optional Settings
ALLOWED_ORIGINS=*
DEBUG=false
LOG_LEVEL=INFO
MAX_DEADLINE_DAYS=365
RELEVANCE_THRESHOLD=2
AI_RATE_LIMIT_SECONDS=5
```

## Usage

### Running the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Running the Pipeline Manually

```bash
python -m app.run_pipeline
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|

| GET | `/api` | Health check |
| GET | `/api/grants` | Retrieve all grants |
| GET | `/api/grants/search?query=<term>` | Search grants by title |
| GET | `/api/grants/{school_name}` | Get grants for a specific school |
| GET | `/api/schools` | Retrieve all schools |
| POST | `/api/email` | Generate email digest for grants |

## Project Structure

```
grants_intelligence_hub/
├── app/
│   ├── main.py              # FastAPI application & endpoints
│   ├── config.py            # Application configuration
│   ├── run_pipeline.py      # Grant scraping pipeline
│   ├── models/              # Pydantic models
│   ├── services/
│   │   ├── scraper_services.py   # Web scraping logic
│   │   ├── filter_service.py     # AI-powered grant filtering
│   │   └── storage_service.py    # Database operations
│   ├── configs/             # Search parameters & filters
│   ├── cache/               # API response cache
│   └── tests/               # Test suite
├── pyproject.toml           # Project dependencies
└── README.md
```

## Pipeline Workflow

1. **Scrape** - Fetches grant listings from search engines based on configured search parameters
2. **Filter** - Processes grants through AI to assess relevance, extract deadlines, and validate data
3. **Store** - Saves filtered grants to Supabase database with school associations

The pipeline runs automatically every Sunday at midnight, or can be triggered manually.

## Testing

```bash
pytest
```

## License

## Authors

Michelle Jemator [https://github.com/Michemor]