import os
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_KEY = os.getenv("APP_KEY")

BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"


def fetch_jobs(job_title: str, location: str, results_per_page: int = 20, page: int = 1):
    if not APP_ID or not APP_KEY:
        return {"error": "Missing APP_ID or APP_KEY in environment (.env)"}

    url = f"https://api.adzuna.com/v1/api/jobs/in/search/{page}"

    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
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

