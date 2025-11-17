import streamlit as st
from main import fetch_jobs
import re
import pandas as pd

st.set_page_config(page_title="JobHarvester", layout="wide")
st.title("JobHarvester 🔍")

# ========== Top Filters ==========
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    job_title = st.text_input("Job Title", "data scientist")

with col2:
    location = st.text_input("Location", "India")

with col3:
    results_per_page = st.number_input(
        "Results", min_value=5, max_value=50, value=20, step=5
    )

col4, col5, col6 = st.columns([2, 2, 2])

with col4:
    min_exp_years = st.slider("Min experience (years)", 0, 10, 0)

with col5:
    skill_filter = st.text_input("Must contain skill (optional)", "")

with col6:
    view_mode = st.radio("View as", ["Cards (2 columns)", "Table"])

search_clicked = st.button("🔍 Search Jobs")


# ========== Helper: extract experience ==========
def extract_experience(text: str):
    match = re.search(r"(\d+)\+?\s+years?", text, flags=re.IGNORECASE)
    if match:
        try:
            num = int(re.search(r"\d+", match.group(0)).group(0))
            return num, match.group(0)
        except Exception:
            return None, match.group(0)
    return None, None


# ========== Main Logic ==========
if search_clicked:
    data = fetch_jobs(job_title, location, results_per_page)

    # Debug helper: always allow you to inspect raw data
    with st.expander("Raw API response (debug)"):
        st.json(data)

    if "error" in data:
        st.error(data["error"])

    elif "results" in data and data["results"]:
        jobs = data["results"]
        st.success(f"Found {len(jobs)} jobs")

        # ---- enrich with parsed experience & skills ----
        skills_keywords = [
            "python", "sql", "machine learning", "deep learning", "nlp",
            "pandas", "numpy", "tensorflow", "pytorch", "spark",
            "statistics", "power bi", "tableau", "aws", "azure",
        ]

        processed_jobs = []
        for job in jobs:
            description = job.get("description", "") or ""

            exp_num, exp_str = extract_experience(description)

            found_skills = [
                s for s in skills_keywords if s.lower() in description.lower()
            ]

            job["_exp_num"] = exp_num
            job["_exp_str"] = exp_str
            job["_skills"] = sorted(set(found_skills))

            processed_jobs.append(job)

        # ---- apply filters ----
        filtered = []
        for job in processed_jobs:
            # experience filter
            if min_exp_years > 0 and job["_exp_num"] is not None:
                if job["_exp_num"] < min_exp_years:
                    continue
            # skill filter
            if skill_filter:
                if skill_filter.lower() not in job.get("description", "").lower():
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
                            "Title": job.get("title", "No Title"),
                            "Company": job.get("company", {})
                            .get("display_name", "N/A"),
                            "Location": job.get("location", {})
                            .get("display_name", "N/A"),
                            "Category": job.get("category", {})
                            .get("label", "N/A"),
                            "Posted": job.get("created", "N/A"),
                            "Experience": job["_exp_str"] or "N/A",
                            "Skills": ", ".join(job["_skills"]),
                            "Apply Link": job.get("redirect_url", ""),
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
                    company = job.get("company", {}).get("display_name", "N/A")
                    location_name = job.get("location", {}).get(
                        "display_name", "N/A"
                    )
                    description = job.get("description", "") or ""
                    category = job.get("category", {}).get("label", "N/A")
                    created = job.get("created", "N/A")
                    redirect_url = job.get("redirect_url", "#")
                    salary_min = job.get("salary_min")
                    salary_max = job.get("salary_max")
                    salary_pred = job.get("salary_is_predicted", "0")
                    skills = job["_skills"]
                    exp_str = job["_exp_str"]

                    st.markdown(f"### {job.get('title', 'No Title')}")
                    st.write(f"**Company:** {company}")
                    st.write(f"**Location:** {location_name}")
                    st.write(f"**Category:** {category}")
                    st.write(f"**Posted:** {created}")

                    # salary
                    if salary_min and salary_max:
                        st.write(f"**Salary:** {salary_min} - {salary_max}")
                    elif salary_pred == "1":
                        st.write("**Salary:** Predicted (no range shown)")
                    else:
                        st.write("**Salary:** Not provided")

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
                    st.write(
                        description[:250]
                        + ("..." if len(description) > 250 else "")
                    )

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

    else:
        st.warning("No results found.")
