# Exams Dashboard

A read-only Streamlit operations dashboard for worksheet 1596592637 in the supplied Google Sheet.

## Run locally

    python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
    .\.venv\Scripts\python -m streamlit run app.py

The first worksheet row is treated as the header; adjust Header row in the sidebar if needed. Values remain formatted text to preserve identifiers, dates, and leading zeroes. The app provides search, record counts, a table, CSV download, and category counts. Refresh data clears the 60-second cache. There is no background polling.

## Connect the sheet

The initial unauthenticated request returned HTTP 401. Choose either method:

### Link viewing

If this data may be shared, open the sheet and select Share > General access > Anyone with the link > Viewer. Click Refresh data in the app. No API key is needed. Organization policies may restrict this option.

### Private sheet

1. Create a Google Cloud project and enable the Google Sheets API.
2. Create a service account and a JSON key.
3. Share the spreadsheet with the service account's client_email as Viewer.
4. Create .streamlit/secrets.toml locally with the fields below from that JSON key. Never commit the real credentials.

```toml
[gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_KEY\n-----END PRIVATE KEY-----\n"
client_email = "YOUR_SERVICE_ACCOUNT_EMAIL"
client_id = "YOUR_CLIENT_ID"
token_uri = "https://oauth2.googleapis.com/token"
```

When these secrets exist the app automatically uses the read-only Sheets API and selects the exact tab by worksheet ID.

## Deploy on Streamlit Community Cloud

1. Push app.py, analytics.py, dashboard_info.py, requirements.txt, README.md, .streamlit/config.toml, and .gitignore to a GitHub repository.
2. Sign in at https://share.streamlit.io and select Create app.
3. Select the repository and branch, and set the entrypoint to app.py.
4. For a private sheet, paste the TOML above with real values into Advanced settings > Secrets. Do not upload secrets.toml to GitHub.
5. Deploy. Use Python 3.12 if selecting a runtime.

Sheet permissions and dashboard visibility are separate: users who can access the dashboard can view the data it loads. Choose suitable app visibility before sharing sensitive records.

Deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
Private sheet guide: https://docs.streamlit.io/develop/tutorials/databases/private-gsheet


## Operations dashboard

Month, client, owner, and overall-status filters drive the KPI cards, owner workload, performance table, process completion, reported cases, owner completion, activity heatmap, and attention list. The monthly comparison uses the three months ending in the selected month and applies the other filters.

One populated exam-code row counts as one operation. Combined codes stay together. The first listed date assigns the month; ambiguous dates are listed in the data-quality panel rather than guessed. Cancelled/discarded operations are excluded. Numeric totals include available numbers only, preserving unknown values as missing.

Done/Sent/No cases are complete. Only Not sent is pending. Blank cells, WIP, non-applicable values, and other notes are ignored in status and completion calculations. Completion = Complete / (Complete + Not sent), across all seven activities. Any Not sent makes the operation or owner/activity Pending; otherwise at least one completed cell makes it Complete. All-ignored operations are N/A (Not evaluated), with no completion percentage. Exam and workload totals still include these operations. Age is days since exam start in India time, not a contractual due date. Future exams do not appear in attention required.

Run calculation checks with `.\.venv\Scripts\python -m unittest test_analytics -v`.


## Dashboard layout

The Info button opens a separate page for calculation rules, data quality, and original filtered records. Filters persist when moving between pages. Download complete data exports all original columns for the filtered rows. Owner performance shows Owner, Exams, Candidates, and Centres. Process completion includes all seven activities. The case table distinguishes impersonation reported and found, with Reported count and Across Exams columns. Attention required shows Owner first and omits Age, Stage, and Sheet note. The standalone owner completion percentage section is removed.
