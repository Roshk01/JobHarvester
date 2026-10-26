import re
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from main import Azuna_fetch_jobs, Serp_fetch_jobs

st.set_page_config(page_title="JobHarvester", layout="wide")
st.title("JobHarvester 🔍")

APP_ID = st.secrets.get("APP_ID")
APP_KEY = st.secrets.get("APP_KEY")
SERP_API_KEY = st.secrets.get("SERP_API_Key")

SENIOR_RE = re.compile(
    r"\b(senior|sr|lead|manager|principal|head|architect|director)\b", re.I
)
EXP_RE = re.compile(
    r"(\d+)\s*(?:\+|-|–|to)?\s*(?:\d+)?\s*\+?\s*(?:years?|yrs?)", re.I
)
SKILLS = [
    "python", "sql", "machine learning", "deep learning", "nlp", "llm",
    "langchain", "rag", "fastapi", "pandas", "numpy", "tensorflow",
    "pytorch", "spark", "statistics", "power bi", "tableau", "aws", "azure",
]

# ========== Filters ==========
c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    job_title = st.text_input("Job Title", "AI ML engineer")
with c2:
    location = st.text_input("Location", "India")
with c3:
    n_results = st.number_input("Results per source", 10, 50, 20, step=10)

c4, c5, c6 = st.columns(3)
with c4:
    max_exp_years = st.slider("Max experience required (years)", 0, 10, 2)
with c5:
    skill_filter = st.text_input("Must contain skill (optional)", "")
with c6:
    view_mode = st.radio("View as", ["Cards (2 columns)", "Table"], horizontal=True)

c7, c8 = st.columns(2)
with c7:
    hide_senior = st.checkbox("Hide senior/lead/manager titles", value=True)
with c8:
    include_unspecified = st.checkbox("Include jobs that don't mention experience", value=True)

search_clicked = st.button("🔍 Search Jobs", type="primary")
st.caption("SerpAPI uses ~1 credit per 10 results. Searches are cached for 1 hour.")


# ========== Helpers ==========
def _ok(res):
    if isinstance(res, dict) and "error" in res:
        raise RuntimeError(res["error"])
    return res


@st.cache_data(ttl=3600, show_spinner=False)
def cached_adzuna(title, loc, n, app_id, app_key):
    return _ok(Azuna_fetch_jobs(title, loc, results_per_page=min(n, 50),
                                app_id=app_id, app_key=app_key))


@st.cache_data(ttl=3600, show_spinner=False)
def cached_serp(title, loc, n, api_key):
    return _ok(Serp_fetch_jobs(title, loc, max_results=n, api_key=api_key))


def parse_date(value):
    """Handles ISO dates (Adzuna) and '3 days ago' (Google Jobs)."""
    if not value:
        return None
    v = str(value).strip().lower()
    m = re.match(r"(\d+)\+?\s*(hour|day|week|month)s?\s+ago", v)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = {"hour": n / 24, "day": n, "week": n * 7, "month": n * 30}[unit]
        return datetime.now() - timedelta(days=days)
    try:
        return datetime.fromisoformat(v.upper().replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def extract_experience(text):
    """Smallest 'N years' found in text -> (number, matched text)."""
    found = [(int(m.group(1)), m.group(0).strip()) for m in EXP_RE.finditer(text or "")]
    return min(found) if found else (None, None)


def normalize_adzuna(j):
    return {
        "title": j.get("title") or "",
        "company": (j.get("company") or {}).get("display_name") or "N/A",
        "location": (j.get("location") or {}).get("display_name") or "N/A",
        "description": j.get("description") or "",
        "posted": j.get("created"),
        "posted_dt": parse_date(j.get("created")),
        "apply_url": j.get("redirect_url"),
        "source": "adzuna",
    }


def normalize_serp(j):
    opts = j.get("apply_options") or []
    url = opts[0].get("link") if opts else j.get("share_link")
    posted = (j.get("detected_extensions") or {}).get("posted_at")
    return {
        "title": j.get("title") or "",
        "company": j.get("company_name") or "N/A",
        "location": j.get("location") or "N/A",
        "description": j.get("description") or "",
        "posted": posted,
        "posted_dt": parse_date(posted),
        "apply_url": url,
        "source": "google_jobs",
    }


def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        key = f"{j['title'].strip().lower()}|{j['company'].strip().lower()}"
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out


# ========== Fetch (only on button click) ==========
if search_clicked:
    jobs = []
    with st.spinner("Fetching jobs..."):
        try:
            res = cached_adzuna(job_title, location, n_results, APP_ID, APP_KEY)
            jobs += [normalize_adzuna(j) for j in res.get("results", [])]
        except Exception as e:
            st.warning(f"Adzuna failed: {e}")
        try:
            res = cached_serp(job_title, location, n_results, SERP_API_KEY)
            jobs += [normalize_serp(j) for j in res.get("jobs_results", [])]
        except Exception as e:
            st.warning(f"SerpAPI failed: {e}")

    jobs = dedupe(jobs)
    jobs.sort(key=lambda x: x["posted_dt"] or datetime.min, reverse=True)
    for j in jobs:
        j["_exp_num"], j["_exp_str"] = extract_experience(j["description"])
        j["_skills"] = sorted(s for s in SKILLS if s in j["description"].lower())
    st.session_state["jobs"] = jobs  # keeps results when you change filters

all_jobs = st.session_state.get("jobs")
if all_jobs is None:
    st.info("Set your filters and click Search Jobs.")
    st.stop()

# ========== Filters apply instantly (no refetch) ==========
filtered = []
for j in all_jobs:
    if hide_senior and SENIOR_RE.search(j["title"]):
        continue
    n = j["_exp_num"]
    if n is None:
        if not include_unspecified:
            continue
    elif n > max_exp_years:
        continue
    if skill_filter and skill_filter.lower() not in j["description"].lower():
        continue
    filtered.append(j)

st.write(f"Showing **{len(filtered)}** of {len(all_jobs)} jobs")
if not filtered:
    st.warning("No jobs match the filters. Try raising max experience.")
    st.stop()

# ========== Table view ==========
if view_mode == "Table":
    df = pd.DataFrame([{
        "Title": j["title"],
        "Company": j["company"],
        "Location": j["location"],
        "Source": j["source"],
        "Posted": j["posted"] or "N/A",
        "Experience": j["_exp_str"] or "N/A",
        "Skills": ", ".join(j["_skills"]),
        "Apply Link": j["apply_url"] or "",
    } for j in filtered])

    st.dataframe(
        df,
        hide_index=True,
        column_config={
            "Apply Link": st.column_config.LinkColumn("Apply Link", display_text="Open ➜")
        },
    )
    st.download_button("Download as CSV", df.to_csv(index=False),
                       file_name="jobs.csv", mime="text/csv")

# ========== Card view ==========
else:
    def render_card(j):
        with st.container(border=True):
            st.markdown(f"### {j['title'] or 'No Title'}")
            st.write(f"**{j['company']}** · {j['location']} · _{j['source']}_")
            st.write(f"**Posted:** {j['posted'] or 'N/A'}")
            st.write(f"**Experience:** {j['_exp_str'] or 'Not mentioned'}")
            st.write("**Skills:** " + (", ".join(j["_skills"]) or "Not detected"))
            with st.expander("Description"):
                st.write(j["description"])
            if j["apply_url"]:
                st.link_button("Apply Now ➜", j["apply_url"])
            else:
                st.caption("No apply link available")

    for i in range(0, len(filtered), 2):
        cols = st.columns(2)
        for k in range(2):
            if i + k < len(filtered):
                with cols[k]:
                    render_card(filtered[i + k])