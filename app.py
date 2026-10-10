import re
from datetime import date, datetime, timezone
import requests
import streamlit as st
import json
from sqlalchemy import create_engine
import pymysql


API_URL = "https://www.arbeitnow.com/api/job-board-api"


# ----------------------------
# MySQL connection
# ----------------------------
def get_connection():
    engine = create_engine("mysql+pymysql://root:mysql12345@localhost/job_search_app")
    return engine.raw_connection()


# ----------------------------
# Fetch jobs from Arbeitnow
# ----------------------------
def fetch_jobs(search_query: str, max_pages: int = 5) -> list[dict]:
    """
    Fetch up to max_pages of Arbeitnow listings.
    The API may ignore the 'search' parameter, so results are also filtered
    locally by filter_jobs().
    """
    jobs = []
    next_url = API_URL
    params = {"search": search_query}

    for page_number in range(max_pages):
        response = requests.get(
            next_url,
            params=params if page_number == 0 else None,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        page_jobs = payload.get("data", [])
        if not isinstance(page_jobs, list):
            break

        jobs.extend(page_jobs)

        # Common paginated API response format. Stop if no next page is given.
        links = payload.get("links") or {}
        next_url = links.get("next")
        if not next_url:
            break

    return jobs


def filter_jobs(
    jobs: list[dict],
    search_query: str,
    location_query: str = "",
    remote_only: bool = False,
) -> list[tuple[dict, float]]:
    """Filter jobs locally and assign a simple demo relevance score."""
    query_terms = [term.lower() for term in re.findall(r"\w+", search_query) if term]
    location_term = location_query.strip().lower()
    matches = []

    for job in jobs:
        title = str(job.get("title") or "")
        company = str(job.get("company_name") or job.get("company") or "")
        description = str(job.get("description") or "")
        location = str(job.get("location") or "")
        tags = job.get("tags") or []
        if isinstance(tags, str):
            tags_text = tags
        elif isinstance(tags, list):
            tags_text = " ".join(str(tag) for tag in tags)
        else:
            tags_text = ""

        searchable = f"{title} {company} {description} {tags_text}".lower()

        # If a query was entered, require at least one query term to match.
        if query_terms and not any(term in searchable for term in query_terms):
            continue

        if location_term and location_term not in location.lower():
            continue

        is_remote = bool(job.get("remote", False))
        if remote_only and not is_remote:
            continue

        # Simple illustrative ranking, not a machine-learning relevance model.
        score = 0.0
        title_lower = title.lower()
        tags_lower = tags_text.lower()
        if search_query.strip().lower() in title_lower:
            score += 60
        if any(term in title_lower for term in query_terms):
            score += 25
        if any(term in tags_lower for term in query_terms):
            score += 15
        if any(term in description.lower() for term in query_terms):
            score += 5
        if is_remote:
            score += 1

        matches.append((job, min(score, 100.0)))

    matches.sort(key=lambda item: item[1], reverse=True)
    return matches


# ----------------------------
# Data conversion helpers
# ----------------------------
def parse_posted_date(value):
    """Convert a Unix timestamp or date-like string into datetime.date."""
    if value is None or value == "":
        return None

    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            return None

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None

    return None


def get_job_external_id(job: dict) -> str:
    """Return a stable unique identifier for the jobs table."""
    value = job.get("slug") or job.get("id") or job.get("url")
    if not value:
        # Last-resort fallback. Prefer API slug/id/url when available.
        value = "|".join(
            [
                str(job.get("title") or ""),
                str(job.get("company_name") or ""),
                str(job.get("location") or ""),
            ]
        )
    return str(value)[:150]


def get_job_tags(job: dict) -> list[str]:
    tags = job.get("tags") or []
    if isinstance(tags, str):
        tags = re.split(r"[,;]", tags)

    if not isinstance(tags, list):
        return []

    # Remove blank and duplicate tags, case-insensitively.
    unique_tags = {}
    for tag in tags:
        cleaned = str(tag).strip()
        if cleaned:
            unique_tags[cleaned.lower()] = cleaned[:100]
    return list(unique_tags.values())


# ----------------------------
# Save data into MySQL tables
# ----------------------------
def save_search_results(
    name: str,
    email: str,
    search_query: str,
    location_query: str,
    remote_only: bool,
    ranked_jobs: list[tuple[dict, float]],
) -> int:
    """
    Save to:
      users, searches, jobs, search_results, skills, job_skills

    Assumes the six tables have the column names shown in your ER diagram
    and have already been created in MySQL.
    Returns the number of matched jobs saved to search_results.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Insert the user, or update their name if this email already exists.
        cursor.execute(
            """
            INSERT INTO users (name, email)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE name = VALUES(name)
            """,
            (name.strip(), email.strip().lower()),
        )
        cursor.execute(
            "SELECT user_id FROM users WHERE email = %s",
            (email.strip().lower(),),
        )
        user_row = cursor.fetchone()
        if not user_row:
            raise RuntimeError("Could not retrieve the user_id.")
        user_id = user_row[0]

        # 2. Store this search.
        cursor.execute(
            """
            INSERT INTO searches (user_id, skill_query, location, remote_only)
            VALUES (%s, %s, %s, %s)
            """,
            (
                user_id,
                search_query.strip(),
                location_query.strip() or None,
                remote_only,
            ),
        )
        search_id = cursor.lastrowid

        saved_count = 0

        for rank, (job, score) in enumerate(ranked_jobs, start=1):
            external_id = get_job_external_id(job)
            title = str(job.get("title") or "Untitled job")[:255]
            company = str(
                job.get("company_name") or job.get("company") or "Unknown company"
            )[:255]
            location = str(job.get("location") or "Not specified")[:255]
            is_remote = bool(job.get("remote", False))
            tags = get_job_tags(job)

            job_types = job.get("job_types") or []
            if isinstance(job_types, list):
                category = ", ".join(str(x) for x in job_types)
            else:
                category = str(job_types or "")
            category = category[:100] or None

            salary_value = job.get("salary")
            salary = str(salary_value)[:255] if salary_value else None
            job_url = str(job.get("url") or "") or None
            description = str(job.get("description") or "")
            posted_date = parse_posted_date(
                job.get("created_at") or job.get("posted_date")
            )

            # 3. Insert the job, updating its details if it already exists.
            cursor.execute(
                """
                INSERT INTO jobs (
                    external_job_id, title, company, location, remote,
                    category, salary, url, description, posted_date
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    company = VALUES(company),
                    location = VALUES(location),
                    remote = VALUES(remote),
                    category = VALUES(category),
                    salary = VALUES(salary),
                    url = VALUES(url),
                    description = VALUES(description),
                    posted_date = VALUES(posted_date)
                """,
                (
                    external_id,
                    title,
                    company,
                    location,
                    is_remote,
                    category,
                    salary,
                    job_url,
                    description,
                    posted_date,
                ),
            )

            cursor.execute(
                "SELECT job_id FROM jobs WHERE external_job_id = %s",
                (external_id,),
            )
            job_row = cursor.fetchone()
            if not job_row:
                continue
            job_id = job_row[0]

            # 4. Save each tag as a skill and link it to the job.
            for tag in tags:
                cursor.execute(
                    """
                    INSERT INTO skills (skill_name)
                    VALUES (%s)
                    ON DUPLICATE KEY UPDATE skill_name = VALUES(skill_name)
                    """,
                    (tag,),
                )
                cursor.execute(
                    "SELECT skill_id FROM skills WHERE skill_name = %s",
                    (tag,),
                )
                skill_row = cursor.fetchone()
                if skill_row:
                    skill_id = skill_row[0]
                    cursor.execute(
                        """
                        INSERT IGNORE INTO job_skills (job_id, skill_id)
                        VALUES (%s, %s)
                        """,
                        (job_id, skill_id),
                    )

            # 5. Link this search to this job and store its rank/score.
            cursor.execute(
                """
                INSERT INTO search_results
                    (search_id, job_id, relevance_score, rank_position)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    relevance_score = VALUES(relevance_score),
                    rank_position = VALUES(rank_position)
                """,
                (search_id, job_id, score, rank),
            )
            saved_count += 1

        conn.commit()
        return saved_count

    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


# ----------------------------
# Streamlit UI
# ----------------------------
st.set_page_config(
    page_title="Job Search & Recommendation",
    page_icon="💼",
    layout="wide",
)

st.title("💼 Job Search & Recommendation App")
st.write("Search job listings and save your search and matching jobs to MySQL.")

with st.form("job_search_form"):
    st.subheader("Your details")
    name = st.text_input("Full name")
    email = st.text_input("Email address")

    st.subheader("Job preferences")
    search_query = st.text_input(
        "Job title or skills",
        placeholder="e.g. iOS Developer, Swift, Python",
    )
    location_query = st.text_input(
        "Location (optional)",
        placeholder="e.g. Bengaluru, India",
    )
    remote_only = st.checkbox("Remote jobs only")

    submitted = st.form_submit_button("Search jobs", type="primary")

if submitted:
    if not name.strip() or not email.strip() or not search_query.strip():
        st.error("Please enter your name, email, and job search query.")
    elif "@" not in email or "." not in email.split("@")[-1]:
        st.error("Please enter a valid email address.")
    else:
        try:
            with st.spinner("Fetching job listings from Arbeitnow..."):
                api_jobs = fetch_jobs(search_query)
                ranked_jobs = filter_jobs(
                    api_jobs,
                    search_query=search_query,
                    location_query=location_query,
                    remote_only=remote_only,
                )

            with st.spinner("Saving your search and jobs to MySQL..."):
                saved_count = save_search_results(
                    name=name,
                    email=email,
                    search_query=search_query,
                    location_query=location_query,
                    remote_only=remote_only,
                    ranked_jobs=ranked_jobs,
                )

            st.success(
                f"Search saved successfully. Found {len(ranked_jobs)} matching "
                f"jobs from {len(api_jobs)} fetched listings; saved {saved_count} "
                "search results to MySQL."
            )

            if ranked_jobs:
                st.subheader("Matching jobs")
                for rank, (job, score) in enumerate(ranked_jobs, start=1):
                    title = job.get("title") or "Untitled job"
                    company = (
                        job.get("company_name")
                        or job.get("company")
                        or "Unknown company"
                    )
                    location = job.get("location") or "Not specified"
                    st.markdown(f"### {rank}. {title}")
                    st.write(f"**Company:** {company}")
                    st.write(f"**Location:** {location}")
                    st.write(f"**Relevance score:** {score:.2f}")
                    if job.get("url"):
                        st.markdown(f"[View / apply for this job]({job['url']})")
                    st.divider()
            else:
                st.info(
                    "No matching jobs were found in the fetched listings. "
                    "Try a broader query or another location."
                )

        except requests.RequestException as exc:
            st.error(f"Could not fetch jobs from Arbeitnow: {exc}")
        except Error as exc:
            st.error(f"MySQL error: {exc}")
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")
