# Data Assets

This folder powers the knowledge layer and the demo.

| Path | Contents |
|---|---|
| `sample_contracts/` | 2 fictional agreements designed to trigger realistic risk flags: `vendor_agreement_sample.txt` (high risk) and `master_services_agreement_sample.txt` |
| `clause_library/clause_library.json` | 20 approved clause templates (indemnity, liability caps, DPDP data protection, arbitration in India, SLAs, IP assignment...) used by RAG retrieval |
| `policy_references/policy_references.json` | 4 approved Tata policy references (procurement compliance, data protection, AI governance, risk-flag guidance) |
| `risk_taxonomy.csv` | 40 risk patterns → severity, rationale, recommendation, confidence, clause_type (used by the offline risk engine) |
| `sample_review_records.csv` | Example reviewer-decision records for reference |

## How to extend

- **Add risk rules**: append rows to `risk_taxonomy.csv` (quote fields containing commas).
- **Add knowledge**: append JSON objects to the clause library / policy files (fields: `kind`, `title`, `category`, `content`, `source`, `approved`, `doc_type`). The RAG index rebuilds automatically on server startup.
- **Add sample documents**: drop files into `sample_contracts/` and re-run `python seed_demo.py`.
