# VisaSponsor AI — approval-based application agent (v3)

An applicant-controlled job discovery and application preparation tool. It retrieves public Greenhouse/Lever employer listings, assigns preliminary role-match scores, records **source-backed sponsorship evidence**, creates a DOCX CV highlights draft, cover letter, evidence report and JSON brief, and maintains a review queue. **It never automatically applies or contacts employers.**

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

1. Add a company's exact public Greenhouse or Lever slug in the sidebar. The project deliberately ships with zero sample postings.
2. Run **Scan configured boards**.
3. Open a job and examine the original employer listing, extracted sponsorship signal and dated source references.
4. Add explicit vacancy-specific sponsorship evidence. Sponsorship history or UK sponsorship licensing **does not** establish that a particular job is sponsored.
5. Generate/download the ZIP application pack. CV and cover letter are **drafts** and must be verified and completed before sending.
6. Set **Approved to apply** only after supporting vacancy-specific evidence exists. Use employer's own application page to submit, then manually mark **Applied**.

## Data and privacy

`data/candidate_profile.json` contains a redacted fact library extracted from four uploaded CV versions. It deliberately omits contact details. Enter contact information in the sidebar during each session. Unconfirmed performance figures must not be used automatically.

The SQLite file defaults to `data/applications.sqlite3`. To keep it outside ephemeral Streamlit hosting, set the `VISASPONSOR_DB_PATH` environment variable to a path on **a persistent, access-controlled volume**. Streamlit Community Cloud local files can be wiped on restart and should not be treated as a durable application database. Running the app locally is the simplest persistent/private initial deployment. **Do not publish your personal profile or application database in a public repository.**

`data/boards.json` is a list of employer-specific public boards. Only genuine jobs retrieved from configured ATS endpoints enter the queue. The daily GitHub Actions scan saves an artifact separately: it does not sync automatically into the Streamlit SQLite database. A sync/persistent cloud service requires further integration.

## Sponsorship logic

- `Explicit role sponsorship`: phrase extracted from the vacancy; still requires immigration eligibility verification.
- `Explicit no sponsorship`: blocks approval unless the employer explicitly confirms an exception for this specific vacancy.
- `Employer licensed / past sponsorship only`: does **not** make a role approvable.
- `Employer confirmed for this vacancy`: manually entered with an attributable URL; user must check it is genuine and current.

No governmental API, sponsor register cross-check, recruiter authentication or immigration legal determination is implemented. The reviewer is responsible for verifying manually entered evidence.

## Document scope

The CV highlights draft **is not a full CV**: it is a concise, truth-constrained starter based on the supplied career profile. It does not fabricate metrics or degree completions. Review or replace it with the master CV before use. Cover letter generation is deterministic, with limited automatic role-specific highlighting; no external LLM or paid API key is necessary.

## Tests

`python -m unittest discover -s tests -v`

## Deployment

A private GitHub repo + Streamlit Cloud or a private machine can run the dashboard (`app.py`). Add supported recruiting boards individually. Set a persistent database path for production. The included GitHub Actions scheduled workflow is an **independent CSV discovery task**, not an automatic applicant or synchronised database task.
