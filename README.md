# Exam Operations Dashboard

Live Google Sheets dashboard with multi-select month, client, owner and status filters; exam and workload cards; completed/WIP process charts and heatmaps; impersonation analytics; outstanding reports; and filtered original-data CSV download.

## Local run

    python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
    .\.venv\Scripts\python -m streamlit run app.py

Run calculation tests:

    .\.venv\Scripts\python -m unittest test_analytics -v

## Streamlit Community Cloud

Repository: AkshayKumarVer/Exams-Dashboard. Branch: main. Entrypoint: app.py. Python: 3.12.

The source sheet uses Anyone with the link / Viewer access. No secrets are needed for this mode. Existing optional service-account authentication remains supported through the gcp_service_account section in Streamlit secrets. Never commit credentials.

Changes pushed to the connected branch trigger a Streamlit rebuild.

Maintainer-only UI information has moved to [ADMIN.md](ADMIN.md). The app does not register a public Info or admin route.
