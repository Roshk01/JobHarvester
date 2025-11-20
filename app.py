import streamlit as st
from main import Azuna_fetch_jobs, Serp_fetch_jobs
import re
import pandas as pd
from datetime import datetime
from typing import Optional

st.set_page_config(page_title="JobHarvester", layout="wide")
st.title("JobHarvester 🔍")

# 🔐 Read secrets from .streamlit/secrets.toml
APP_ID = st.secrets.get("APP_ID")
APP_KEY = st.secrets.get("APP_KEY")
SERP_API_KEY = st.secrets.get("SERP_API_Key")

# ========== Top Filters ==========
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    job_title = st.text_input("Job Title", "data scientist")

with col2:
    location = st.text_input("Location", "India")

with col3:
    results_per_page = st.number_input(
        "Results per source", min_value=5, max_value=50, value=20, step=5
    )

col4, col5, col6 = st.columns([2, 2, 2])

with col4:
    min_exp_years = st.slider("Min experience (years)", 0, 10, 0)

with col5:
    skill_filter = st.text_input("Must contain skill (optional)", "")

with col6:
    view_mode = st.radio("View as", ["Cards (2 columns)", "Table"])

search_clicked = st.button("🔍 Search Jobs")


# ========== Helper functions ==========
def extract_experience(text: str):
    match = re.search(r"(\d+)\+?\s+years?", text or "", flags=re.IGNORECASE)
    if match:
        try:
            num = int(re.search(r"\d+", match.group(0)).group(0))
            return num, match.group(0)
        except Exception:
            return None, match.group(0)
    return None, None


def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    # Try common ISO formats, fallback to None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    # last fallback: try fromisoformat (may fail on Z)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_adzuna_job(j: dict) -> dict:
    """Turn an Adzuna job item into our common schema."""
    return {
        "title": j.get("title"),
        "company": j.get("company", {}).get("display_name"),
        "location": j.get("location", {}).get("display_name"),
        "description": j.get("description", "") or "",
        "created": j.get("created"),  # ISO string usually
        "created_dt": parse_date(j.get("created")),
        "apply_url": j.get("redirect_url") or j.get("redirect_url"),
        "source": "adzuna",
        "raw": j,
    }


def normalize_serp_job(j: dict) -> dict:
    """Turn a SerpApi job item into our common schema.
       Adjust keys depending on the exact Serp response shape."""
    # Serp items sometimes have 'title', 'link' or 'apply_link' or 'redirect_url'
    title = j.get("title") or j.get("job_title")
    company = j.get("company_name") or (j.get("hiring_organization") and j["hiring_organization"].get("name")) or j.get("company")
    location = j.get("location") or j.get("location_name") or j.get("candidate_required_location")
    description = j.get("description") or j.get("snippet") or ""
    created = j.get("posted_at") or j.get("created") or j.get("date") or j.get("date_posted")
    apply_url = j.get("apply_link") or j.get("link") or j.get("url") or j.get("redirect_url")

    return {
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "created": created,
        "created_dt": parse_date(created),
        "apply_url": apply_url,
        "source": "serpapi",
        "raw": j,
    }


def dedupe_jobs(jobs: list) -> list:
    """Simple dedupe by (title, company, location, apply_url) lowered keys."""
    seen = set()
    out = []
    for j in jobs:
        key = (
            (j.get("apply_url") or "").strip().lower()
            or f"{(j.get('title') or '').strip().lower()}|{(j.get('company') or '').strip().lower()}|{(j.get('location') or '').strip().lower()}"
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


# ========== Main Logic ==========
if search_clicked:
    # fetch from both sources (pass secrets)
    azd_raw = Azuna_fetch_jobs(job_title, location, results_per_page, app_id=APP_ID, app_key=APP_KEY)
    serp_raw = Serp_fetch_jobs(job_title, location, results_per_page, api_key=SERP_API_KEY)

    # Debug: show raw responses so you can inspect shapes
    with st.expander("Raw Adzuna response (debug)"):
        st.json(azd_raw)
    with st.expander("Raw SerpApi response (debug)"):
        st.json(serp_raw)

    # Normalize lists
    azd_jobs = []
    if isinstance(azd_raw, dict) and azd_raw.get("results"):
        for item in azd_raw.get("results", []):
            azd_jobs.append(normalize_adzuna_job(item))
    elif isinstance(azd_raw, list):
        for item in azd_raw:
            azd_jobs.append(normalize_adzuna_job(item))

    serp_jobs = []
    # Serp response can contain jobs under 'jobs_results' or 'jobs' or be a list
    if isinstance(serp_raw, dict):
        serp_list = serp_raw.get("jobs_results") or serp_raw.get("jobs") or serp_raw.get("results") or []
    elif isinstance(serp_raw, list):
        serp_list = serp_raw
    else:
        serp_list = []

    for item in serp_list:
        serp_jobs.append(normalize_serp_job(item))

    # Merge + dedupe
    all_jobs = azd_jobs + serp_jobs
    all_jobs = dedupe_jobs(all_jobs)

    # Sort by created_dt (newest first). If missing date, treat as older.
    all_jobs.sort(key=lambda x: x.get("created_dt") or datetime.min, reverse=True)

    st.success(f"Aggregated {len(all_jobs)} jobs (after dedupe & sort)")

    # ---- enrich with parsed experience & skills ----
    skills_keywords = [
        "python", "sql", "machine learning", "deep learning", "nlp",
        "pandas", "numpy", "tensorflow", "pytorch", "spark",
        "statistics", "power bi", "tableau", "aws", "azure",
    ]

    for job in all_jobs:
        desc = job.get("description") or ""
        exp_num, exp_str = extract_experience(desc)
        job["_exp_num"] = exp_num
        job["_exp_str"] = exp_str
        job["_skills"] = sorted({s for s in skills_keywords if s.lower() in desc.lower()})

    # ---- apply filters ----
    filtered = []
    for job in all_jobs:
        # experience filter
        if min_exp_years > 0 and job["_exp_num"] is not None:
            if job["_exp_num"] < min_exp_years:
                continue
        # skill filter
        if skill_filter:
            if skill_filter.lower() not in (job.get("description") or "").lower():
                continue
        filtered.append(job)

    st.write(f"Showing {len(filtered)} jobs after filters")

    if not filtered:
        st.warning("No jobs match the filters.")
    else:
        # ====== TABLE VIEW ======
        if view_mode == "Table":
            rows = []
            for job in filtered:
                rows.append(
                    {
                        "Title": job.get("title") or "No Title",
                        "Company": job.get("company") or "N/A",
                        "Location": job.get("location") or "N/A",
                        "Source": job.get("source"),
                        "Posted": job.get("created") or "N/A",
                        "Experience": job["_exp_str"] or "N/A",
                        "Skills": ", ".join(job["_skills"]),
                        "Apply Link": job.get("apply_url") or "",
                    }
                )

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "Apply Link": st.column_config.LinkColumn(
                        label="Apply Link",
                        display_text="Open ➜",
                    )
                },
            )

            csv = df.to_csv(index=False)
            st.download_button(
                "Download as CSV",
                data=csv,
                file_name="jobs.csv",
                mime="text/csv",
            )

        # ====== CARD VIEW (2 columns) ======
        else:

            def render_card(job):
                company = job.get("company") or "N/A"
                location_name = job.get("location") or "N/A"
                description = job.get("description") or ""
                source = job.get("source") or "N/A"
                created = job.get("created") or "N/A"
                redirect_url = job.get("apply_url") or "#"
                skills = job["_skills"]
                exp_str = job["_exp_str"]

                st.markdown(f"### {job.get('title', 'No Title')}")
                st.write(f"**Company:** {company}  ·  **Source:** {source}")
                st.write(f"**Location:** {location_name}")
                st.write(f"**Posted:** {created}")

                # experience
                if exp_str:
                    st.write(f"**Experience (parsed):** {exp_str}")
                else:
                    st.write("**Experience:** Not clearly mentioned")

                # skills
                if skills:
                    st.write("**Skills (detected):** " + ", ".join(skills))
                else:
                    st.write("**Skills:** Not auto-detected")

                # description
                st.markdown("**Description (preview):**")
                st.write(description[:250] + ("..." if len(description) > 250 else ""))

                # ✅ Apply button (styled, opens in new tab)
                st.markdown(
                    f"""
                    <a href="{redirect_url}" target="_blank" style="text-decoration:none;">
                        <div style="
                            background-color:#0A66C2;
                            color:white;
                            padding:10px 18px;
                            text-align:center;
                            border-radius:8px;
                            font-size:16px;
                            font-weight:600;
                            margin-top:10px;
                            display:inline-block;
                        ">
                            Apply Now ➜
                        </div>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )

            # 2-column grid
            for i in range(0, len(filtered), 2):
                cols = st.columns(2)
                for col_idx in range(2):
                    if i + col_idx < len(filtered):
                        with cols[col_idx]:
                            render_card(filtered[i + col_idx])
