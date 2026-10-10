# Streamlit App : https://jobsearch-crkijd288ynslfyc6a452s.streamlit.app

# Job Search App

A Python-based job search application built with Streamlit. The app retrieves job listings from the Arbeitnow Job Board API and helps users search for relevant opportunities using keywords and other filters.

## Features

* Search for jobs using keywords.
* Filter job listings by location.
* Identify remote job opportunities.
* Retrieve job listings from the Arbeitnow Job Board API.
* Display job titles, company names, locations, descriptions, and application links.
* Connect to a MySQL database to store job-related information.
* Track job search and application details.

## Technologies Used

* **Python** — Application logic
* **Streamlit** — Web interface
* **Requests** — API communication
* **MySQL** — Database storage
* **Arbeitnow Job Board API** — Job listing data

## API Used

The application retrieves job listings from the following API:

https://www.arbeitnow.com/api/job-board-api

The API provides information about job postings, including job titles, company names, locations, descriptions, remote-work availability, tags, and original job posting URLs.

## Project Structure

```text
JobSearch/
├── app.py
├── requirements.txt
├── .gitignore
└── README.md
```

Additional files or folders may be present depending on your project configuration.

## Prerequisites

Before running the application, ensure you have installed:

* Python 3.10 or later
* pip
* MySQL Server, if the application uses database functionality

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/kavyajeergi/JobSearch.git
cd JobSearch
```

### 2. Create a virtual environment

On macOS:

```bash
python3 -m venv .venv
```

### 3. Activate the virtual environment

```bash
source .venv/bin/activate
```

### 4. Install dependencies

If `requirements.txt` exists:

```bash
pip install -r requirements.txt
```

Otherwise, install the main packages:

```bash
pip install streamlit requests mysql-connector-python
```

Install the MySQL connector only if it is the connector used in your application.

### 5. Configure the database

If your app uses MySQL, configure the database connection using the credentials and settings expected by `app.py`.

Keep database passwords in a local configuration or secrets file. Do not commit credentials to GitHub.

### 6. Run the application

```bash
streamlit run app.py
```

Open the local URL displayed in the terminal, usually:

http://localhost:8501

## Usage

1. Start the Streamlit application.
2. Enter the job search keyword.
3. Provide a location or select the available filters.
4. Browse the matching job listings.
5. Review job descriptions and company information.
6. Open the original job posting link to apply.
7. Use the database functionality provided by the application to save or track job information, where configured.

## Error Handling and Troubleshooting

* **Module not found:** Activate your virtual environment and install the required dependencies.
* **MySQL connection error:** Verify that MySQL is running and that the database credentials are correct.
* **No job results:** Try a broader keyword or location.
* **API request error:** Check your internet connection and the availability of the Arbeitnow API.
* **Streamlit command not found:** Activate `.venv` and install Streamlit.

## Git Configuration

Add the following entries to the root-level `.gitignore` file to avoid committing local files:

```gitignore
.venv/
__pycache__/
*.py[cod]
.DS_Store
.vscode/settings.json
.streamlit/secrets.toml
```

## GitHub Repository

https://github.com/kavyajeergi/JobSearch

## License

This project is intended for learning and personal development. Add a license file if you plan to distribute it publicly.
