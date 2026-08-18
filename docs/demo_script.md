# Demo Script

Target: **≤ 3 minutes**. Shows the full journey: upload → OCR → parsing → clause extraction → RAG retrieval → legal reasoning → risk flags → summary → human approval → audit.

---

## 0. Prepare

1. Start the app: `python run.py` → open http://localhost:8000
2. (Optional) Pre-load samples: `python seed_demo.py`
3. Have `data/sample_contracts/vendor_agreement_sample.txt` ready to drag in.

## 1. Login (0:15)
- Open the app → robotic login terminal.
- Enter `admin@tata.com` / `tata123` → INITIALIZE SESSION.
- Point out the "AI MODE" LED in the sidebar (green = Gemini, amber = offline engine).

## 2. Dashboard (0:30)
- KPI row: Total Documents, Completed, % Completion, Processing, High Risk.
- "x high-risk contracts need review" alert banner → click **Review now**.
- Processing pipeline stats (avg. analysis time, queue, AI accuracy) + Risk Category Matrix.
- Recent Documents table with Status + Risk badges.

## 3. Upload (0:50)
- Open **Upload Document**.
- Drag `vendor_agreement_sample.txt` (or a PDF). Fill doc type = Vendor Agreement, Business Unit = Legal, counterparty, jurisdiction = USA, Confidentiality = Confidential, Priority = High.
- Click **TRANSMIT DOCUMENT** → auto-redirects to Processing.

## 4. Processing Pipeline (1:10)
- Show the live stage list: OCR → Parsing → Clause Extraction → RAG Retrieval → Legal Reasoning → Risk Flagging → Summarization → Review.
- Highlight stage detail lines (e.g. `clauses=16`, `flags=7 high=3`).
- Auto-refreshes until complete; final status `UNDER REVIEW` / `ATTENTION`.

## 5. Review & Risk (1:50)
- **AI Summary**: read parties, term, governing law, obligations, risks — note "PENDING LEGAL REVIEW" label.
- **Extracted Clauses**: show Indemnification, Limitation of Liability, Termination, Non-Compete with page + confidence.
- **Risk Flags**: pick a flag and walk through the four parts:
  - Severity badge (High) · category (Unilateral Indemnity)
  - Rationale (one-sided indemnity)
  - Evidence (exact clause text quoted)
  - Confidence % + recommendation (→ negotiate mutual indemnity)
- Click **APPROVE** (or escalate one flag first).

## 6. Audit (2:20)
- Open **Audit History**: show pipeline_start → stages → review_approve entries with actors and timestamps.

## 7. Close (2:40)
- Summarize value: faster first-pass review, grounded reasoning, explainable risk flags, human-in-the-loop governance.

---

## Expected outputs for the bundled sample

| Asset | Expected result |
|---|---|
| `vendor_agreement_sample.txt` | ~16 clauses, ~7 risk flags (3 High): Unilateral Indemnity, Auto-Renewal Trap, Non-Compete Too Broad, plus Medium/Low flags |
| `master_services_agreement_sample.txt` | Lower risk profile; flags such as Restrictive Audit Window, Termination Fee, long non-renewal notice |
| RAG query "indemnity liability vendor" | Tata Group Vendor Risk Policy, Procurement Compliance Manual, Insurance requirements |
