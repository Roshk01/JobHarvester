import os
import requests
from dotenv import load_dotenv
from serpapi import GoogleSearch
load_dotenv()

Azuna_BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search"
Serp_BASE_URL = "https://serpapi.com/search.json?"
serp_api_key = os.getenv("SERP_API_Key")
Azuna_APP_ID = os.getenv("Azuna_APP_ID")
Azuna_APP_KEY = os.getenv("APP_KEY")

# Azuna fetch jobs function

def Azuna_fetch_jobs(job_title: str, location: str, results_per_page: int = 20, page: int = 1,
               app_id: str | None = None, app_key: str | None = None):
    # Fallback to environment variables if not provided
    if app_id is None:
        app_id = os.getenv("Azuna_APP_ID")
    if app_key is None:
        app_key = os.getenv("Azuna_APP_KEY")

    if not app_id or not app_key:
        return {"error": "Missing APP_ID or APP_KEY (provide via Streamlit secrets or environment variables)."}

    url = f"{Azuna_BASE_URL}/{page}"

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

# serp fetch jobs function

def Serp_fetch_jobs(job_title: str, location: str, results_per_page: int = 10,
               api_key: str | None = None):
    # Fallback to environment variables if not provided
    if api_key is None:
        api_key = serp_api_key

    if not api_key:
        return {"error": "Missing SERP_API_Key (provide via Streamlit secrets or environment variables)."}

    url = "https://serpapi.com/search.json?"

    params = {
        "engine": "google_jobs",
        "q": job_title,
        "location": location,
        "api_key": api_key,
        "num": results_per_page
    }

    try:
        res = GoogleSearch(params).get_dict()
        return res
    except requests.RequestException as e:
        return {"error": f"Failed to fetch jobs: {e}"}
    

# if __name__ == "__main__":
#     title = input("Enter job title: ")
#     loc = input("Enter location: ")

#     result = Serp_fetch_jobs(title, loc, results_per_page=10)
#     print(result)
