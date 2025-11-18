import os
import requests

BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search"


def fetch_jobs(job_title: str, location: str, results_per_page: int = 20, page: int = 1,
               app_id: str | None = None, app_key: str | None = None):
    # Fallback to environment variables if not provided
    if app_id is None:
        app_id = os.getenv("APP_ID")
    if app_key is None:
        app_key = os.getenv("APP_KEY")

    if not app_id or not app_key:
        return {"error": "Missing APP_ID or APP_KEY (provide via Streamlit secrets or environment variables)."}

    url = f"{BASE_URL}/{page}"

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": job_title,
        "where": location,
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        return {"error": f"Failed to fetch jobs: {e}"}
